# Third-party release notices

`licenses/` contains original licence/notice files copied from the exact publisher wheels selected in `requirements-arm64.lock`. The external wheelhouse retains each wheel's complete metadata and embedded libraries. `evidence/ARM64_WHEELS.json` records publisher URLs, hashes, versions and licence declarations. A hash is an integrity check, not a new licence grant or publisher signature.

Application and vendored project source retain their original rights. No new public distribution licence for project source is invented here. Neural weights are separate existing local assets; the application archive includes their hashes and expected filenames, not model binaries or a transfer of model rights. Review each upstream model's actual licence before distributing models outside the user's existing private project.

The matched XMOS host executable, USB library and firmware command map are not distributed by this release. A separately built and verified ARM64 host bundle is required for Linux hardware use; follow the vendor sources in PI_DEPLOYMENT_WORKFLOW.md. No XVF firmware is flashed by these tools.
