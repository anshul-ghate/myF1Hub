"""
Deployment Preparation Script for F1 HUB
Run this before deploying to check readiness.
"""

import os
from pathlib import Path

def check_streamlit_secrets():
    """Check if Streamlit secrets are configured."""
    secrets_file = Path(".streamlit/secrets.toml")
    
    if not secrets_file.exists():
        print("[WARNING] .streamlit/secrets.toml not found")
        print("  For local testing, copy secrets.toml.example to secrets.toml")
        print("  For production, add secrets in Streamlit Community Cloud UI")
        return False
    
    print("[OK] Secrets file found")
    return True

def check_gitignore():
    """Verify sensitive files are in .gitignore."""
    gitignore = Path(".gitignore")
    
    if not gitignore.exists():
        print("[ERROR] .gitignore not found!")
        return False
    
    content = gitignore.read_text(encoding='utf-8')
    required_entries = [".env", ".streamlit/secrets.toml", "f1_cache"]
    
    missing = [entry for entry in required_entries if entry not in content]
    
    if missing:
        print(f"[WARNING] Missing in .gitignore: {', '.join(missing)}")
        return False
    
    print("[OK] .gitignore properly configured")
    return True

def check_requirements():
    """Check if requirements.txt exists."""
    req_file = Path("requirements.txt")
    
    if not req_file.exists():
        print("[ERROR] requirements.txt not found!")
        return False
    
    print("[OK] requirements.txt found")
    return True

def check_config():
    """Check if Streamlit config exists."""
    config_file = Path(".streamlit/config.toml")
    
    if not config_file.exists():
        print("[WARNING] .streamlit/config.toml not found (optional)")
        return False
    
    print("[OK] Streamlit config found")
    return True

def check_main_file():
    """Check if main entry point exists."""
    main_file = Path("app/main.py")
    
    if not main_file.exists():
        print("[ERROR] app/main.py not found!")
        return False
    
    print("[OK] Main application file found")
    return True

def main():
    """Run all deployment readiness checks."""
    print("=" * 60)
    print("F1 HUB - Deployment Readiness Check")
    print("=" * 60)
    print()
    
    checks = [
        ("Main file", check_main_file),
        ("Requirements", check_requirements),
        ("Gitignore", check_gitignore),
        ("Streamlit config", check_config),
        ("Secrets", check_streamlit_secrets),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\nChecking: {name}")
        print("-" * 40)
        result = check_func()
        results.append((name, result))
    
    print("\n" + "=" * 60)
    print("DEPLOYMENT READINESS REPORT")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "[PASS]" if result else "[NEEDS ATTENTION]"
        print(f"{status}: {name}")
    
    print(f"\nScore: {passed}/{total} checks passed")
    
    if passed >= total - 1:  # Allow one optional warning
        print("\nYour app is ready for deployment!")
        print("\nNext steps:")
        print("1. Push your code to GitHub")
        print("2. Go to share.streamlit.io")
        print("3. Connect your repository")
        print("4. Add secrets in app settings")
        print("5. Deploy!")
    else:
        print("\nPlease address the issues above before deploying.")
        print("See DEPLOYMENT.md for detailed instructions.")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
