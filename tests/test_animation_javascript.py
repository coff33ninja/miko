"""
Simple test to verify JavaScript animation files are properly structured.

This test validates the JavaScript files without requiring the full Flask app setup.
"""

import os
import re
import json
from pathlib import Path


class TestJavaScriptAnimationFiles:
    """Test JavaScript animation files for syntax and structure."""

    def setup_method(self):
        """Set up test fixtures."""
        self.js_dir = Path("src/web/static/js")

    def test_javascript_files_exist(self):
        """Test that all required JavaScript files exist."""
        required_files = [
            "live2d-integration.js",
            "animation-controller.js",
            "live2d-parameter-mapping.js",
            "animation-tests.js",
        ]

        for filename in required_files:
            file_path = self.js_dir / filename
            assert file_path.exists(), f"Required file {filename} does not exist"
            assert file_path.stat().st_size > 0, f"File {filename} is empty"

    def test_live2d_integration_structure(self):
        """Test Live2D integration file structure."""
        file_path = self.js_dir / "live2d-integration.js"
        content = file_path.read_text(encoding="utf-8")

        # Check for main class definition
        assert "class Live2DIntegration" in content

        # Check for essential methods
        essential_methods = [
            "triggerAnimation",
            "startMouthSync",
            "stopMouthSync",
            "mapSentimentToExpression",
            "setParameter",
            "getParameter",
        ]

        for method in essential_methods:
            assert method in content, f"Method {method} not found in Live2DIntegration"

    def test_animation_controller_structure(self):
        """Test Animation Controller file structure."""
        file_path = self.js_dir / "animation-controller.js"
        content = file_path.read_text(encoding="utf-8")

        # Check for main classes
        assert "class AnimationController" in content
        assert "class SentimentAnalyzer" in content

        # Check for essential methods
        essential_methods = [
            "handleAIResponse",
            "handleUserInput",
            "handleTTSStart",
            "handleTTSEnd",
            "triggerContextualAnimation",
        ]

        for method in essential_methods:
            assert (
                method in content
            ), f"Method {method} not found in AnimationController"

    def test_parameter_mapping_structure(self):
        """Test Parameter Mapping file structure."""
        file_path = self.js_dir / "live2d-parameter-mapping.js"
        content = file_path.read_text(encoding="utf-8")

        # Check for main class
        assert "class Live2DParameterMapping" in content

        # Check for essential methods
        essential_methods = [
            "getExpressionParameters",
            "validateParameter",
            "calculateMouthSyncParameters",
            "generateBreathingParameters",
            "interpolateParameters",
        ]

        for method in essential_methods:
            assert (
                method in content
            ), f"Method {method} not found in Live2DParameterMapping"

    def test_animation_tests_structure(self):
        """Test Animation Tests file structure."""
        file_path = self.js_dir / "animation-tests.js"
        content = file_path.read_text(encoding="utf-8")

        # Check for test classes
        assert "class AnimationTestSuite" in content
        assert "class AnimationIntegrationTest" in content

        # Check for test methods
        test_methods = [
            "testBasicAnimationTrigger",
            "testParameterUpdates",
            "testExpressionMapping",
            "testMouthSynchronization",
            "testSentimentAnalysis",
        ]

        for method in test_methods:
            assert method in content, f"Test method {method} not found"

    def test_javascript_syntax_basic(self):
        """Basic JavaScript syntax validation."""
        js_files = [
            "live2d-integration.js",
            "animation-controller.js",
            "live2d-parameter-mapping.js",
            "animation-tests.js",
        ]

        for filename in js_files:
            file_path = self.js_dir / filename
            content = file_path.read_text(encoding="utf-8")

            # Check for balanced braces
            open_braces = content.count("{")
            close_braces = content.count("}")
            assert open_braces == close_braces, f"Unbalanced braces in {filename}"

            # Check for balanced parentheses in function definitions
            function_matches = re.findall(r"function\s+\w+\s*\([^)]*\)", content)
            method_matches = re.findall(r"\w+\s*\([^)]*\)\s*{", content)

            # Should have some function/method definitions
            assert (
                len(function_matches) + len(method_matches) > 0
            ), f"No functions found in {filename}"

    def test_expression_mapping_completeness(self):
        """Test that expression mapping covers all required expressions."""
        file_path = self.js_dir / "live2d-parameter-mapping.js"
        content = file_path.read_text(encoding="utf-8")

        required_expressions = [
            "neutral",
            "happy",
            "sad",
            "angry",
            "surprised",
            "speak",
        ]

        for expression in required_expressions:
            assert (
                f"'{expression}'" in content
            ), f"Expression {expression} not found in mapping"

    def test_parameter_definitions(self):
        """Test that standard Live2D parameters are defined."""
        file_path = self.js_dir / "live2d-parameter-mapping.js"
        content = file_path.read_text(encoding="utf-8")

        required_parameters = [
            "ParamAngleX",
            "ParamAngleY",
            "ParamAngleZ",
            "ParamEyeLOpen",
            "ParamEyeROpen",
            "ParamMouthForm",
            "ParamMouthOpenY",
            "ParamBrowLY",
            "ParamBrowRY",
        ]

        for param in required_parameters:
            assert (
                f"'{param}'" in content
            ), f"Parameter {param} not found in definitions"

    def test_event_listeners_setup(self):
        """Test that event listeners are properly set up."""
        file_path = self.js_dir / "animation-controller.js"
        content = file_path.read_text(encoding="utf-8")

        # Check for event listener setup
        assert "addEventListener" in content

        # Check for custom events
        custom_events = [
            "aiResponseReceived",
            "userInputReceived",
            "ttsStarted",
            "ttsEnded",
        ]

        for event in custom_events:
            assert event in content, f"Event {event} not found in controller"

    def test_error_handling_present(self):
        """Test that error handling is implemented."""
        js_files = [
            "live2d-integration.js",
            "animation-controller.js",
            "animation-tests.js",
        ]

        for filename in js_files:
            file_path = self.js_dir / filename
            content = file_path.read_text(encoding="utf-8")

            # Check for try-catch blocks
            assert "try {" in content, f"No try-catch blocks found in {filename}"
            assert "catch" in content, f"No catch blocks found in {filename}"

            # Check for error logging
            assert "console.error" in content, f"No error logging found in {filename}"

    def test_window_exports(self):
        """Test that classes are properly exported to window object."""
        expected_exports = {
            "live2d-integration.js": ["Live2DIntegration"],
            "animation-controller.js": ["AnimationController", "SentimentAnalyzer"],
            "live2d-parameter-mapping.js": ["Live2DParameterMapping"],
            "animation-tests.js": ["AnimationTestSuite", "AnimationIntegrationTest"],
        }

        for filename, exports in expected_exports.items():
            file_path = self.js_dir / filename
            content = file_path.read_text(encoding="utf-8")

            for export_name in exports:
                assert (
                    f"window.{export_name}" in content
                ), f"Export {export_name} not found in {filename}"


class TestLive2DModelFiles:
    """Test Live2D model files and configuration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.models_dir = Path("src/web/static/models")
        self.expressions_dir = Path("src/web/static/expressions")

    def test_model_files_exist(self):
        """Test that Live2D model files exist."""
        required_files = ["Poblanc.model3.json", "Poblanc.moc3"]

        for filename in required_files:
            file_path = self.models_dir / filename
            assert file_path.exists(), f"Model file {filename} does not exist"

    def test_model_configuration_valid(self):
        """Test that model configuration is valid JSON."""
        model_file = self.models_dir / "Poblanc.model3.json"

        if model_file.exists():
            content = model_file.read_text(encoding="utf-8")

            # Should be valid JSON
            try:
                model_config = json.loads(content)
            except json.JSONDecodeError as e:
                assert False, f"Invalid JSON in model file: {e}"

            # Check required fields
            assert "Version" in model_config
            assert "FileReferences" in model_config

            # Check file references
            file_refs = model_config["FileReferences"]
            assert "Moc" in file_refs
            assert "Textures" in file_refs

    def test_expression_files_exist(self):
        """Test that expression files exist and are valid."""
        if self.expressions_dir.exists():
            expression_files = list(self.expressions_dir.glob("*.exp3.json"))

            for expr_file in expression_files:
                content = expr_file.read_text(encoding="utf-8")

                # Should be valid JSON
                try:
                    expr_config = json.loads(content)
                except json.JSONDecodeError as e:
                    assert (
                        False
                    ), f"Invalid JSON in expression file {expr_file.name}: {e}"

                # Check required fields
                assert "Type" in expr_config
                assert expr_config["Type"] == "Live2D Expression"
                assert "Parameters" in expr_config


class TestHTMLIntegration:
    """Test HTML template integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.template_file = Path("src/web/templates/index.html")

    def test_html_template_exists(self):
        """Test that HTML template exists."""
        assert self.template_file.exists(), "HTML template does not exist"
        assert self.template_file.stat().st_size > 0, "HTML template is empty"

    def test_javascript_includes(self):
        """Test that JavaScript files are included in HTML."""
        content = self.template_file.read_text(encoding="utf-8")

        required_scripts = [
            "live2d-parameter-mapping.js",
            "live2d-integration.js",
            "animation-controller.js",
            "animation-tests.js",
        ]

        for script in required_scripts:
            assert script in content, f"Script {script} not included in HTML template"

    def test_canvas_element_present(self):
        """Test that Live2D canvas element is present."""
        content = self.template_file.read_text(encoding="utf-8")

        assert 'id="live2d-canvas"' in content, "Live2D canvas element not found"
        assert "<canvas" in content, "Canvas element not found"

    def test_animation_controls_present(self):
        """Test that animation control buttons are present."""
        content = self.template_file.read_text(encoding="utf-8")

        control_functions = [
            "triggerAnimation('happy')",
            "triggerAnimation('sad')",
            "triggerAnimation('angry')",
            "triggerAnimation('surprised')",
            "triggerAnimation('neutral')",
            "triggerAnimation('speak')",
        ]

        for control in control_functions:
            assert control in content, f"Animation control {control} not found"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
