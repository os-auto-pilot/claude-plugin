#!/bin/bash
# Inject the properties cleanly at launch
export PLATFORM_API_URL="http://localhost:8000"
export EXECUTION_API_URL="http://localhost:3232"
export BACKEND_URL="http://localhost:8088"
export PLATFORM_API_KEY="Oniesoft@123dfgewerrt"
export PLATFORM_COMPANY_ID="43e4f7c3-1a17-4627-8d95-49fd59076851"
export PLATFORM_PROJECT_ID="248af507-c75c-4590-95b8-4145891df8d0"
export PLATFORM_USER_ID="15eb541f-2dbe-403f-8191-9e1ad15fc0ef"

# Launch your python script passing down these exact environment maps
bash /Users/prakash/Documents/oniesoft/auto-pilot-claude-plugin/scripts/resolve-python.sh /Users/prakash/Documents/oniesoft/auto-pilot-claude-plugin/server/launch.py
