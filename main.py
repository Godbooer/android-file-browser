import sys
import os

# Add current dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import AndroidFileBrowserApp

if __name__ == '__main__':
    AndroidFileBrowserApp().run()
