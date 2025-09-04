#!/usr/bin/env python3
"""
Configuration validation script for Anime AI Character system.
Validates all required environment variables and system dependencies.
"""

import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import subprocess

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from config.settings import load_config, ConfigurationError
except ImportError as e:
    print(f"❌ Failed to import configuration module: {e}")
    print("Make sure you're running this from the project root directory.")
    sys.exit(1)


class ConfigValidator:
    """Validates system configuration and dependencies."""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
    
    def add_error(self, message: str):
        """Add an error message."""
        self.errors.append(message)
    
    def add_warning(self, message: str):
        """Add a warning message."""
        self.warnings.append(message)
    
    def add_info(self, message: str):
        """Add an info message."""
        self.info.append(message)
    
    def validate_python_version(self):
        """Validate Python version requirements."""
        if sys.version_info < (3, 8):
            self.add_error(f"Python 3.8+ required, found {sys.version_info.major}.{sys.version_info.minor}")
        else:
            self.add_info(f"✅ Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    def validate_required_files(self):
        """Validate required files exist."""
        required_files = [
            ".env",
            ".env.example", 
            "main.py",
            "requirements.txt",
            "src/config/settings.py"
        ]
        
        for file_path in required_files:
            if not Path(file_path).exists():
                if file_path == ".env":
                    self.add_error(f"Missing {file_path} - copy .env.example to .env and configure")
                else:
                    self.add_error(f"Missing required file: {file_path}")
            else:
                self.add_info(f"✅ Found: {file_path}")
    
    def validate_directories(self):
        """Validate required directories exist or can be created."""
        required_dirs = [
            "src",
            "static",
            "static/models", 
            "logs",
            "scripts"
        ]
        
        for dir_path in required_dirs:
            path = Path(dir_path)
            if not path.exists():
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    self.add_info(f"✅ Created directory: {dir_path}")
                except Exception as e:
                    self.add_error(f"Failed to create directory {dir_path}: {e}")
            else:
                self.add_info(f"✅ Directory exists: {dir_path}")
    
    def validate_dependencies(self):
        """Validate Python package dependencies."""
        try:
            # Check if requirements.txt exists
            if not Path("requirements.txt").exists():
                self.add_warning("No requirements.txt found - cannot validate dependencies")
                return
            
            # Try to import key packages
            required_packages = [
                ("dotenv", "python-dotenv"),
                ("livekit", "livekit"),
                ("flask", "Flask"),
                ("asyncio", "built-in")
            ]
            
            for package, pip_name in required_packages:
                try:
                    __import__(package)
                    self.add_info(f"✅ Package available: {package}")
                except ImportError:
                    if pip_name != "built-in":
                        self.add_warning(f"Package not found: {package} (install with: uv add {pip_name})")
                    else:
                        self.add_error(f"Built-in package not available: {package}")
        
        except Exception as e:
            self.add_warning(f"Could not validate dependencies: {e}")
    
    def validate_configuration(self):
        """Validate application configuration."""
        try:
            config = load_config()
            self.add_info("✅ Configuration loaded successfully")
            
            # Validate AI provider configuration
            if config.ai.use_ollama:
                self.add_info(f"✅ AI Provider: Ollama ({config.ai.ollama_model})")
                self.add_info(f"   Host: {config.ai.ollama_host}")
            else:
                if config.ai.gemini_api_keys:
                    self.add_info(f"✅ AI Provider: Gemini ({len(config.ai.gemini_api_keys)} keys)")
                else:
                    self.add_error("Gemini selected but no API keys provided")
            
            # Validate LiveKit configuration
            if config.livekit.url and config.livekit.api_key and config.livekit.api_secret:
                self.add_info(f"✅ LiveKit configured: {config.livekit.url}")
                self.add_info(f"   Room: {config.livekit.room_name}")
            else:
                self.add_error("LiveKit configuration incomplete")
            
            # Validate memory configuration
            if config.memory.mem0_api_key:
                self.add_info(f"✅ Memory: Mem0 ({config.memory.mem0_collection})")
            else:
                self.add_warning("No Mem0 API key - memory will be session-only")
            
            # Validate Live2D configuration
            self.add_info(f"✅ Live2D model: {config.live2d.model_url}")
            
            # Validate Flask configuration
            self.add_info(f"✅ Flask server: {config.flask.host}:{config.flask.port}")
            
        except ConfigurationError as e:
            self.add_error(f"Configuration validation failed: {e}")
        except Exception as e:
            self.add_error(f"Unexpected error validating configuration: {e}")
    
    def validate_network_connectivity(self):
        """Validate network connectivity to external services."""
        # This is optional and can be skipped if network is not available
        try:
            import urllib.request
            import socket
            
            # Test basic internet connectivity
            try:
                urllib.request.urlopen('https://www.google.com', timeout=5)
                self.add_info("✅ Internet connectivity available")
            except:
                self.add_warning("No internet connectivity - external services may not work")
            
        except ImportError:
            self.add_warning("Cannot test network connectivity - urllib not available")
    
    def run_validation(self) -> bool:
        """Run all validation checks.
        
        Returns:
            bool: True if validation passed (no errors), False otherwise
        """
        print("🔍 Validating Anime AI Character system configuration...")
        print("=" * 60)
        
        # Run all validation checks
        self.validate_python_version()
        self.validate_required_files()
        self.validate_directories()
        self.validate_dependencies()
        self.validate_configuration()
        self.validate_network_connectivity()
        
        # Print results
        print("\n📊 VALIDATION RESULTS")
        print("=" * 60)
        
        if self.info:
            print("\n✅ SUCCESS:")
            for msg in self.info:
                print(f"   {msg}")
        
        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for msg in self.warnings:
                print(f"   {msg}")
        
        if self.errors:
            print("\n❌ ERRORS:")
            for msg in self.errors:
                print(f"   {msg}")
        
        print("\n" + "=" * 60)
        
        if self.errors:
            print("❌ VALIDATION FAILED - Please fix the errors above")
            return False
        elif self.warnings:
            print("⚠️  VALIDATION PASSED WITH WARNINGS - System should work but check warnings")
            return True
        else:
            print("✅ VALIDATION PASSED - System is ready to run!")
            return True


def main():
    """Main validation entry point."""
    validator = ConfigValidator()
    
    try:
        success = validator.run_validation()
        
        if success:
            print("\n💡 To start the system, run: python main.py")
            sys.exit(0)
        else:
            print("\n💡 Fix the errors above and run validation again")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error during validation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()