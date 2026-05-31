# Cleanup and Retention

No auto DELETE for old news/digest/history.

## Permanent retention (must preserve)
- published history
- source/link/title/body/full_text
- digest history
- admin actions
- source registry/source health
- send attempts
- llm runs

## Disposable
- tmp files
- audio intermediates
- cache
- oversized logs after rotation

## Migration policy
- dry-run by default
- production mutation false
- backup before any real migration command
- explicit operator command required for real migration/cutover
