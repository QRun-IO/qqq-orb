# QQQ Orb Development Makefile
# Provides convenient commands for orb development, validation, and publishing

.PHONY: help pack validate clean test test-scripts test-all publish-snapshot publish-release dev check-clean check-branch

# Default target
help:
	@echo "QQQ Orb Development Commands:"
	@echo ""
	@echo "  make pack           		- Pack the orb using 'orb pack' (recommended for orb development)"
	@echo "  make validate       		- Validate the packed orb"
	@echo "  make test           		- Pack and validate the orb"
	@echo "  make test-scripts   		- Run comprehensive tests for calculate_version.sh"
	@echo "  make test-all       		- Run all tests (orb + scripts)"
	@echo "  make clean          		- Remove packed orb files"
	@echo "  make dev            		- Development workflow: pack, validate, and show status"
	@echo "  make lint           		- Run all CircleCI-style linting checks"
	@echo "  make publish-snapshot 	- Interactive snapshot release (dev:snapshot)"
	@echo "  make publish-release  	- Interactive production release (tagged version)"
	@echo ""
	@echo "Key Files:"
	@echo "  src/@orb.yml           		- Main orb definition"
	@echo "  target/qqq-orb-packed.yml 	- Packed orb (generated)"

# Pack the orb using the correct command for orb development
pack:
	@echo "Packing orb using 'circleci orb pack'..."
	@mkdir -p ./target/
	@circleci orb pack src > target/qqq-orb-packed.yml
	@echo "✅ Orb packed successfully: target/qqq-orb-packed.yml"

# Validate the packed orb
validate: pack
	@echo "Validating packed orb..."
	@circleci orb validate target/qqq-orb-packed.yml
	@echo "✅ Orb validation successful"

# Test workflow: pack and validate
test: validate
	@echo "✅ All tests passed!"

# Test scripts: run comprehensive tests for calculate_version.sh
test-scripts:
	@echo "🧪 Running calculate_version.sh test suite..."
	@./tests/run_tests.sh --ci
	@echo "✅ Script tests passed!"

# Test all: run both orb tests and script tests
test-all: test test-scripts
	@echo "🎉 All tests completed successfully!"

# Clean up generated files
clean:
	@echo "Cleaning up packed orb files..."
	@rm -rf target
	@echo "✅ Cleanup complete"

# Lint source files (same checks as CircleCI)
lint:
	@echo "🔍 Running CircleCI-style linting checks..."
	@echo ""
	@echo "1. YAML Linting..."
	@yamllint src/commands/ src/jobs/ src/examples/ src/@orb.yml
	@echo "✅ YAML linting passed"
	@echo ""
	@echo "2. Shell Script Linting (ShellCheck)..."
	@shellcheck src/scripts/*.sh
	@echo "✅ Source script ShellCheck passed"
	@echo ""
	@echo "3. Test Script Linting (ShellCheck)..."
	@shellcheck tests/*.sh
	@echo "✅ Test script ShellCheck passed"
	@echo ""
	@echo "4. CircleCI Orb Linting..."
	@circleci orb validate src/@orb.yml
	@echo "✅ CircleCI orb validation passed"
	@echo ""
	@echo "5. Orb Packing Test..."
	@circleci orb pack src > /tmp/test-packed.yml
	@circleci orb validate /tmp/test-packed.yml
	@rm -f /tmp/test-packed.yml
	@echo "✅ Orb packing test passed"
	@echo ""
	@echo "🎉 All linting checks passed! Ready for commit."
	@echo ""
	@echo "Note: For orb best practices review (orb-tools/review),"
	@echo "      this runs automatically in CircleCI when you push."

# Development workflow: pack, validate, and show status
dev: validate
	@echo ""
	@echo "🎉 Development Status:"
	@echo "  ✅ Orb packed successfully"
	@echo "  ✅ Orb validation passed"
	@echo "  📁 Packed orb: target/qqq-orb-packed.yml"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Review the packed orb: cat target/qqq-orb-packed.yml"
	@echo "  2. Test with a project configuration"
	@echo "  3. Publish when ready:"
	@echo "     - make publish-snapshot  (for dev testing)"
	@echo "     - make publish-release   (for production)"

# Check if working directory is clean
check-clean:
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "❌ Working directory is not clean. Commit changes first."; \
		exit 1; \
	fi

# Check if we're on the right branch for releases
check-branch:
	@current=$$(git branch --show-current); \
	if [ "$$current" != "main" ] && [ "$$current" != "master" ]; then \
		echo "⚠️  Warning: You're on branch '$$current', not main/master"; \
		echo "   This is recommended for production releases."; \
		read -p "Continue anyway? [y/N]: " confirm; \
		if [ "$$confirm" != "y" ] && [ "$$confirm" != "Y" ]; then \
			exit 1; \
		fi; \
	fi

# Interactive snapshot release (dev:snapshot)
publish-snapshot: check-clean lint validate
	@echo "🚀 Publishing Snapshot Release"
	@echo ""
	@echo "This will publish to: kingsrook/qqq-orb@dev:snapshot"
	@echo ""
	@read -p "Continue with snapshot release? [y/N]: " confirm; \
	if [ "$$confirm" != "y" ] && [ "$$confirm" != "Y" ]; then \
		echo "❌ Release cancelled"; \
		exit 1; \
	fi; \
	echo ""; \
	echo "📦 Publishing snapshot..."; \
	circleci orb publish target/qqq-orb-packed.yml kingsrook/qqq-orb@dev:snapshot; \
	echo "✅ Snapshot published successfully!"

# Interactive production release (tagged version)
publish-release: check-clean check-branch lint validate
	@echo "🚀 Publishing Production Release"
	@echo ""
	@echo "This will create a git tag and publish a production version."
	@echo ""
	@latest=$$(git tag -l 'v*' | sort -V | tail -1); \
	if [ -n "$$latest" ]; then \
		echo "Latest version: $$latest"; \
		next=$$(echo "$$latest" | sed 's/^v//' | awk -F. '{$$NF++; print $$1"."$$2"."$$NF}'); \
		echo "Suggested next version: v$$next"; \
	else \
		echo "No previous versions found. Starting with v0.1.0"; \
		next="0.1.0"; \
	fi; \
	echo ""; \
	read -p "Enter version [v$$next]: " version; \
	version=$${version:-v$$next}; \
	if [ "$$version" != "v$$(echo $$version | sed 's/^v//')" ]; then \
		echo "❌ Version must start with 'v' (e.g., v1.0.0)"; \
		exit 1; \
	fi; \
	if git tag -l | grep -q "^$$version$$"; then \
		echo "❌ Tag $$version already exists"; \
		exit 1; \
	fi; \
	echo ""; \
	echo "Creating tag $$version..."; \
	git tag -a "$$version" -m "Release $$version"; \
	echo "Publishing kingsrook/qqq-orb@$$(echo $$version | sed 's/^v//')..."; \
	circleci orb publish target/qqq-orb-packed.yml kingsrook/qqq-orb@$$(echo $$version | sed 's/^v//'); \
	echo "Pushing tag to remote..."; \
	git push origin "$$version"; \
	echo "✅ Production release $$version published successfully!"
