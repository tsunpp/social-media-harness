# Package Namespace Migration Plan

The distribution is named `social-media-harness`, but version 0.1.x exposes the generic top-level Python package `app`. Renaming it in place would break imports, entrypoints, and downstream installations, so the change is deferred to the next compatibility-breaking release.

## Target

- Distribution name: `social-media-harness`
- Python package: `social_media_harness`
- CLI entrypoint: `smh = social_media_harness.engine_cli_v2_6:main`

## Migration requirements

1. Move reusable modules from `src/app/` to `src/social_media_harness/`.
2. Convert internal imports to the new namespace.
3. Provide a temporary `app` compatibility shim that emits a deprecation warning.
4. Test both old and new imports for one transition release.
5. Update examples, console entrypoints, package data, and clean-install tests.
6. Remove the compatibility shim only in a later release with an explicit migration note.

This is a planned 0.2.x change, not a safe patch for 0.1.1.
