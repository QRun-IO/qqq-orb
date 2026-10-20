# IntelliJ plugin native standard

The plugin is a real resource-only product, not a no-CI exemption. Its native
profile is `intellij-plugin`, with an orb-owned reusable worker and canonical
auxiliary bridge at `.github/workflows/build.yml`. Generate using
`generate_auxiliary_workflow.py intellij-plugin --ref IMMUTABLE_ORB_SHA`.

PRs and main/develop/tag pushes use Linux/JDK17 and the committed Gradle wrapper
(Gradle8.6 in audited source) to run `check buildPlugin`. Distribution ZIPs and
reports are retained. There are no authored source tests in the audited product;
this validates its actual Gradle packaging lifecycle without inventing app code.
No consumer build.gradle.kts semantics are changed.

Publication remains opt-in manual: select `vVERSION`, set publish=true and the
exact source version, then approve the `intellij-marketplace` environment. The
worker requires successful same-source build, exact source version/tag/HEAD and
remote tag identity, serializes publication, requires all four existing secret
interfaces, then executes `signPlugin publishPlugin`. Secrets CERTIFICATE_CHAIN,
PRIVATE_KEY, PRIVATE_KEY_PASSWORD and PUBLISH_TOKEN are passed only into that
step. Ordinary builds and PRs never publish. The caller and worker need only
contents:read; Marketplace authorization remains the existing token contract.

Root must configure/verify environment protection and existing secret availability,
run the hosted build canary, and verify signed Marketplace release separately.
No credentials, consumer migration or publication have been performed here.
Version1.1.0 is already documented historically: do not republish it merely to
test automation. The vVERSION convention is the explicit new guarded CI release
contract, not a claim about historical tags. No GitHub release is synthesized.
