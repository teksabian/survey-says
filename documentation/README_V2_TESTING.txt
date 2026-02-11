FAMILY FEUD V2 - LOCAL TESTING GUIDE
=====================================

🚀 SUPER SIMPLE START:
----------------------
1. Double-click: START_V2_LOCAL.bat
2. Wait for "Running on http://127.0.0.1:5000"
3. Open browser: http://localhost:5000
4. Test the PowerPoint upload!


📋 FIRST TIME SETUP:
--------------------
Only need to do this ONCE:

Open Command Prompt in this folder and run:
    pip install -r requirements.txt

That's it! Now you can use the batch file anytime.


🧪 TESTING THE PPTX FIX:
-------------------------
1. Run START_V2_LOCAL.bat
2. Go to host dashboard
3. Upload your .pptx or .pptm file
4. Check if all 8 rounds are created!


❓ TROUBLESHOOTING:
-------------------
"Python not found":
    - Make sure Python is installed
    - Try: python --version

"Module not found":
    - Run: pip install -r requirements.txt

"Port 5000 in use":
    - Close any other Family Feud instances
    - Or change port in app.py


📦 WHAT'S IN V2.0.0-ALPHA:
---------------------------
✅ Fixed PowerPoint parser
   - Now correctly extracts all answers with counts
   - Tested with your template file

Coming soon:
⏳ AI scoring system
⏳ Winner announcements


VERSION: V2.0.0-ALPHA
STATUS: PowerPoint Parser Fixed ✅
