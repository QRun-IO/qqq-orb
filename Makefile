# QQQ Orb Development Makefile
# Provides convenient commands for orb development, validation, and publishing

.PHONY: help pack validate clean test publish dev

# Default target
help:
	@echo "QQQ Orb Development Commands:"
	@echo ""
	@echo "  make pack      - Pack the orb using 'orb pack' (recommended for orb development)"
	@echo "  make validate  - Validate the packed orb"
	@echo "  make test      - Pack and validate the orb"
	@echo "  make clean     - Remove packed orb files"
	@echo "  make dev       - Development workflow: pack, validate, and show status"
	@echo "  make publish   - Show publishing instructions (requires manual steps)"
	@echo ""
	@echo "Key Files:"
	@echo "  src/@orb.yml           - Main orb definition"
	@echo "  target/qqq-orb-packed.yml - Packed orb (generated)"

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

# Clean up generated files
clean:
	@echo "Cleaning up packed orb files..."
	@rm -rf target
	@echo "✅ Cleanup complete"

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
	@echo "  3. Publish when ready: make publish"

# Show publishing instructions
publish:
	@echo "🚀 Orb Publishing Instructions:"
	@echo ""
	@echo "1. Ensure you're logged in to CircleCI CLI:"
	@echo "   circleci auth login"
	@echo ""
	@echo "2. Build the orb first (if not already done):"
	@echo "   make dev"
	@echo ""
	@echo "3. Publish the orb:"
	@echo "   circleci orb publish target/qqq-orb-packed.yml kingsrook/qqq-orb@dev:alpha"
	@echo ""
	@echo "4. For production release:"
	@echo "   circleci orb publish target/qqq-orb-packed.yml kingsrook/qqq-orb@2.1.0"
	@echo ""
	@echo "5. Promote dev version to production:"
	@echo "   circleci orb publish promote kingsrook/qqq-orb@dev:alpha patch"
	@echo ""
	@echo "📚 More info: https://circleci.com/docs/orb-author/#publishing-an-orb"
