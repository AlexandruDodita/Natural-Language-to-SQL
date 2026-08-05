"""PostgreSQL MCP server package — the thesis's baseline comparison arm.

See README.md for what this is and how to run it. The two entry points an
evaluation harness typically needs:

    from mcps.postgres.client_harness import ask, ask_async
    from mcps.postgres import db  # for in-process introspection/queries
"""
