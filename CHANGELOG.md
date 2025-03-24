# 2025-03-25
- Added `run.py` and recommend as the default entrypoint.  It should do better to make sure everyone has the proper requirements and python version installed.

# 2025-03-22
- Major new interactive terminal UI mostly thanks to @AdiWeit. Allows downloading multiple urls at once, extracting matterport embeds, renaming, deleting, and launching models from the interface

# 2025-01-24
- Added embedded attachment / 'matterport tags' downloading for things like image points

## 2025-01-10
- Local cropped mesh_tile image generation leads to much higher dollhouse views and fixes some texture errors

## 2024-12-30
- Basic defurnished model support, nearly all excess 403/404 requests eliminated

## 2024-12-25
- Major changes to frontend from matterport including stricter access key requirements, access keys for javascript files, and multiple other changes.  Major restructuring of matterport-dl.py to avoid brute force methods and properly harvest nearly all resource data we need to download.  No longer using every access key we know if failure, but instead using the correct access key per resource.  This should speed up runs a good bit by cutting the # of requests down.

## 2024-09-14
- Downloading models from behind the great china firewall added through their matterportvr.cn server

## 2024-08-19
- New auto-serve option to start server and optionally launch browser (with fix for Windows browsers)
- Sample [Auto PY to EXE](https://github.com/brentvollebregt/auto-py-to-exe) config added for standalone executable generation
- `defaults.json` support for default command line options

## 2024-08-10
- Disable SSL verification for easier proxy use
- Extended encoding support (matterport unicode scaping embedded JS on non-english pages)
- Download static files/photos using graphql data as old keys not reliable
- New expiry code defeat and fix some expiry dates also not replaced


## 2024-08-03
- JS network proxy to leave most code unmodified but still redirect
- Downloading of plugins and other advanced matterport features like floor plan sq/ft and other settings
- VR support
- Lower cpu usage during initial capture
- Ability to set the directory for downloads
- Further download progress details
- No-tilde in path to assist non-windows platform downloads
- Save copy of matterport-dl.py and the JS Proxy next to the model for enhanced compatibility.
