#!/usr/bin/env python3
"""
Deployment script for Anime AI Character system.
Handles Docker deployment, configuration validation, and service management.
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path
from typing import List, Optional
import json
import time

class DeploymentManager:
    """Manages deployment operations for the Anime AI Character system."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.project_root = Path(__file__).parent.parent
        os.chdir(self.project_root)
    
    def log(self, message: str, level: str = "INFO"):
        """Log a message with timestamp."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        prefix = {
            "INFO": "ℹ️",
            "SUCCESS": "✅", 
            "WARNING": "⚠️",
            "ERROR": "❌",
            "DEBUG": "🔍"
        }.get(level, "ℹ️")
        
        print(f"[{timestamp}] {prefix} {message}")
        
        if self.verbose and level == "DEBUG":
            print(f"    Debug: {message}")
    
    def run_command(self, command: List[str], check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess:
        """Run a shell command with logging."""
        cmd_str = " ".join(command)
        self.log(f"Running: {cmd_str}", "DEBUG")
        
        try:
            result = subprocess.run(
                command,
                check=check,
                capture_output=capture_output,
                text=True,
                cwd=self.project_root
            )
            
            if capture_output and result.stdout:
                self.log(f"Output: {result.stdout.strip()}", "DEBUG")
            
            return result
        except subprocess.CalledProcessError as e:
            self.log(f"Command failed: {cmd_str}", "ERROR")
            if e.stdout:
                self.log(f"Stdout: {e.stdout}", "ERROR")
            if e.stderr:
                self.log(f"Stderr: {e.stderr}", "ERROR")
            raise
    
    def validate_prerequisites(self):
        """Validate deployment prerequisites."""
        self.log("Validating deployment prerequisites...")
        
        # Check Docker
        try:
            result = self.run_command(["docker", "--version"], capture_output=True)
            self.log(f"Docker version: {result.stdout.strip()}", "SUCCESS")
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("Docker is not installed or not accessible")
        
        # Check Docker Compose
        try:
            result = self.run_command(["docker", "compose", "version"], capture_output=True)
            self.log(f"Docker Compose version: {result.stdout.strip()}", "SUCCESS")
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("Docker Compose is not installed or not accessible")
        
        # Check required files
        required_files = [".env", "Dockerfile", "docker-compose.yml", "requirements.txt"]
        for file_path in required_files:
            if not Path(file_path).exists():
                if file_path == ".env":
                    raise RuntimeError("No .env file found. Copy .env.example to .env and configure your settings.")
                else:
                    raise RuntimeError(f"Required file missing: {file_path}")
        
        self.log("Prerequisites validation completed", "SUCCESS")
    
    def validate_configuration(self):
        """Validate application configuration."""
        self.log("Validating application configuration...")
        
        try:
            # Run the configuration validator
            result = self.run_command([
                sys.executable, "scripts/validate_config.py"
            ], capture_output=True)
            
            self.log("Configuration validation passed", "SUCCESS")
            
        except subprocess.CalledProcessError as e:
            self.log("Configuration validation failed", "ERROR")
            if e.stdout:
                print(e.stdout)
            if e.stderr:
                print(e.stderr)
            raise RuntimeError("Configuration validation failed")
    
    def build_images(self, no_cache: bool = False):
        """Build Docker images."""
        self.log("Building Docker images...")
        
        build_args = ["docker", "compose", "build"]
        if no_cache:
            build_args.append("--no-cache")
        
        self.run_command(build_args)
        self.log("Docker images built successfully", "SUCCESS")
    
    def start_services(self, detached: bool = True, profiles: Optional[List[str]] = None):
        """Start application services."""
        self.log("Starting application services...")
        
        up_args = ["docker", "compose", "up"]
        
        if profiles:
            for profile in profiles:
                up_args.extend(["--profile", profile])
        
        if detached:
            up_args.append("-d")
        
        self.run_command(up_args)
        
        if detached:
            self.log("Services started in detached mode", "SUCCESS")
            self.show_status()
        else:
            self.log("Services started in foreground mode", "SUCCESS")
    
    def stop_services(self):
        """Stop application services."""
        self.log("Stopping application services...")
        
        self.run_command(["docker", "compose", "down"])
        self.log("Services stopped successfully", "SUCCESS")
    
    def restart_services(self):
        """Restart application services."""
        self.log("Restarting application services...")
        
        self.run_command(["docker", "compose", "restart"])
        self.log("Services restarted successfully", "SUCCESS")
    
    def show_status(self):
        """Show service status."""
        self.log("Service status:")
        
        try:
            result = self.run_command(["docker", "compose", "ps"], capture_output=True)
            print(result.stdout)
        except subprocess.CalledProcessError:
            self.log("Failed to get service status", "ERROR")
    
    def show_logs(self, service: Optional[str] = None, follow: bool = False):
        """Show service logs."""
        logs_args = ["docker", "compose", "logs"]
        
        if follow:
            logs_args.append("-f")
        
        if service:
            logs_args.append(service)
        
        self.run_command(logs_args)
    
    def cleanup(self, volumes: bool = False):
        """Clean up Docker resources."""
        self.log("Cleaning up Docker resources...")
        
        # Stop and remove containers
        self.run_command(["docker", "compose", "down"])
        
        # Remove images
        try:
            self.run_command(["docker", "compose", "down", "--rmi", "all"])
        except subprocess.CalledProcessError:
            self.log("Some images could not be removed", "WARNING")
        
        # Remove volumes if requested
        if volumes:
            try:
                self.run_command(["docker", "compose", "down", "--volumes"])
                self.log("Volumes removed", "SUCCESS")
            except subprocess.CalledProcessError:
                self.log("Some volumes could not be removed", "WARNING")
        
        self.log("Cleanup completed", "SUCCESS")
    
    def deploy(self, build: bool = True, no_cache: bool = False, profiles: Optional[List[str]] = None):
        """Full deployment process."""
        self.log("Starting deployment process...")
        
        try:
            # Validate prerequisites
            self.validate_prerequisites()
            
            # Validate configuration
            self.validate_configuration()
            
            # Build images if requested
            if build:
                self.build_images(no_cache=no_cache)
            
            # Start services
            self.start_services(profiles=profiles)
            
            # Wait a moment for services to start
            time.sleep(5)
            
            # Show final status
            self.show_status()
            
            self.log("Deployment completed successfully!", "SUCCESS")
            self.log("Access the application at: http://localhost:5000", "INFO")
            
        except Exception as e:
            self.log(f"Deployment failed: {e}", "ERROR")
            raise


def main():
    """Main deployment script entry point."""
    parser = argparse.ArgumentParser(description="Deploy Anime AI Character system")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Deploy command
    deploy_parser = subparsers.add_parser("deploy", help="Full deployment")
    deploy_parser.add_argument("--no-build", action="store_true", help="Skip building images")
    deploy_parser.add_argument("--no-cache", action="store_true", help="Build without cache")
    deploy_parser.add_argument("--profile", action="append", help="Docker Compose profiles to activate")
    
    # Build command
    build_parser = subparsers.add_parser("build", help="Build Docker images")
    build_parser.add_argument("--no-cache", action="store_true", help="Build without cache")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start services")
    start_parser.add_argument("--foreground", action="store_true", help="Run in foreground")
    start_parser.add_argument("--profile", action="append", help="Docker Compose profiles to activate")
    
    # Stop command
    subparsers.add_parser("stop", help="Stop services")
    
    # Restart command
    subparsers.add_parser("restart", help="Restart services")
    
    # Status command
    subparsers.add_parser("status", help="Show service status")
    
    # Logs command
    logs_parser = subparsers.add_parser("logs", help="Show service logs")
    logs_parser.add_argument("service", nargs="?", help="Specific service to show logs for")
    logs_parser.add_argument("-f", "--follow", action="store_true", help="Follow log output")
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean up Docker resources")
    cleanup_parser.add_argument("--volumes", action="store_true", help="Also remove volumes")
    
    # Validate command
    subparsers.add_parser("validate", help="Validate configuration only")
    
    # Global options
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        manager = DeploymentManager(verbose=args.verbose)
        
        if args.command == "deploy":
            manager.deploy(
                build=not args.no_build,
                no_cache=args.no_cache,
                profiles=args.profile
            )
        elif args.command == "build":
            manager.validate_prerequisites()
            manager.build_images(no_cache=args.no_cache)
        elif args.command == "start":
            manager.validate_prerequisites()
            manager.start_services(
                detached=not args.foreground,
                profiles=args.profile
            )
        elif args.command == "stop":
            manager.stop_services()
        elif args.command == "restart":
            manager.restart_services()
        elif args.command == "status":
            manager.show_status()
        elif args.command == "logs":
            manager.show_logs(service=args.service, follow=args.follow)
        elif args.command == "cleanup":
            manager.cleanup(volumes=args.volumes)
        elif args.command == "validate":
            manager.validate_prerequisites()
            manager.validate_configuration()
        
    except KeyboardInterrupt:
        print("\n🛑 Operation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()