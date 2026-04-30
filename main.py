"""
Android File Browser - Entry Point
"""
import sys
import os

# Ensure app module can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import AndroidFileBrowserApp

# Direct module-level run() call for p4a parser compatibility
app = AndroidFileBrowserApp()

if __name__ == '__main__':
    app.run()
