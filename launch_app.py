"""Bootstrapper for Streamlit app - changes to correct directory first."""
import os, sys

# Change to the app directory
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "windows-rag-system"))

# Fix sys.argv for Streamlit
port = os.environ.get("PORT", "8501")
sys.argv = ["streamlit", "run", "app.py", "--server.port", port, "--server.headless", "true"]

# Import and run streamlit
import streamlit.web.cli
streamlit.web.cli.main()
