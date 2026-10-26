@echo off
echo ===================================================
echo Running Automated Test Suite & End-to-End Demo
echo ===================================================
python -m pytest tests/test_core.py -v
echo.
python tests/test_end_to_end_flow.py
echo.
echo ===================================================
echo All tests finished.
echo ===================================================
pause
