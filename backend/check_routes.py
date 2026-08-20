#!/usr/bin/env python3
import sys
sys.stdout.reconfigure(encoding='utf-8')

from app.main import app

print("All registered routes containing /user:")
for route in app.routes:
    if hasattr(route, 'path') and '/user' in route.path:
        methods = getattr(route, 'methods', set())
        print(f"  {methods} {route.path}")
