#!/usr/bin/env python3
"""Read one Sonatype deployment status without retrying or publishing anything."""
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request

ENDPOINT = "https://central.sonatype.com/api/v1/publisher/status"
STATES = {"PENDING", "VALIDATING", "VALIDATED", "PUBLISHING", "PUBLISHED", "FAILED"}
UUID = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def error_categories(errors):
    """Emit only fixed labels, never server-supplied keys or descriptions."""
    text = json.dumps(errors).lower()
    categories = [name for name in (
        "signature", "checksum", "namespace", "javadoc", "sources", "license", "pom"
    ) if name in text]
    return categories or ["validation"]


def validation_details(errors, environment):
    # Only validation errors, never the full response or request/headers.
    secrets = [str(v) for k, v in environment.items()
               if v and any(part in k.upper() for part in ("TOKEN", "PASSWORD", "PASSPHRASE", "SECRET", "PRIVATE_KEY"))]
    pair = environment.get("CENTRAL_USERNAME", "") + ":" + environment.get("CENTRAL_PASSWORD", "")
    secrets.extend([pair, base64.b64encode(pair.encode()).decode()])
    details = json.dumps(errors, ensure_ascii=True)
    for secret in sorted(secrets, key=len, reverse=True):
        details = details.replace(secret, "<REDACTED>")
    details = re.sub(r"(?i)(?:bearer|basic)\s+[A-Za-z0-9+/=._-]+", "<REDACTED>", details)
    return details[:12000]


def read_status(environment, open_request=None):
    deployment = environment.get("QQQ_CENTRAL_DEPLOYMENT_ID", "")
    result = {"error_categories": []}

    def fail(category):
        result["error_categories"] = [category]
        return 1, result

    if not UUID.fullmatch(deployment):
        return fail("invalid_deployment_id")
    deployment = deployment.lower()
    result["deploymentId"] = deployment
    username = environment.get("CENTRAL_USERNAME", "")
    password = environment.get("CENTRAL_PASSWORD", "")
    if not username or not password:
        return fail("missing_credentials")
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(
        ENDPOINT + "?id=" + deployment, data=b"", method="POST",
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
    )
    if open_request is None:
        open_request = urllib.request.build_opener(NoRedirects()).open
    try:
        with open_request(request, timeout=30) as response:
            raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                return fail("invalid_response")
            data = json.loads(raw)
    except urllib.error.HTTPError as error:
        category = ("authentication" if error.code == 401 else
                    "authorization" if error.code == 403 else
                    "redirect_rejected" if 300 <= error.code < 400 else "http_error")
        error.close()
        return fail(category)
    except (urllib.error.URLError, TimeoutError, OSError):
        return fail("transport")
    except (ValueError, UnicodeError):
        return fail("invalid_response")
    if not isinstance(data, dict):
        return fail("invalid_response")
    returned_id = data.get("deploymentId")
    if not isinstance(returned_id, str) or returned_id.lower() != deployment:
        return fail("deployment_id_mismatch")
    state = data.get("deploymentState")
    if not isinstance(state, str) or state not in STATES:
        return fail("invalid_state")
    result["deploymentState"] = state
    if state == "FAILED":
        result["error_categories"] = error_categories(data.get("errors"))
        result["validation_details"] = validation_details(data.get("errors"), environment)
        return 1, result
    return (0 if state == "PUBLISHED" else 2), result


def main():
    code, result = read_status(os.environ)
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
