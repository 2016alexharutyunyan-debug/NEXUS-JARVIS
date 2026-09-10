JARVIS 2.4.3 / PRESERVED REACTOR LOCATION HUD

Extract the full ZIP to a new folder. Run INSTALL_JARVIS.bat if needed,
then START_JARVIS.bat. Keep your personal keys in your local voice settings.

MY LOCATION
Say "my location", "show my location", "where am I", or "location hud".
The original screenshot layout is preserved: full dark/cyan map, upper-left
readout, zoom/recenter controls, and animated JARVIS core at lower-right.
The map uses OpenStreetMap, not Google tiles, to retain the supplied design.
No API key is needed for this mode.

Allow the session prompt to request your device position from Windows.
Enable Windows Settings > Privacy & security > Location > Location services
and desktop app location access if necessary. The location-options icon in
the map toolbar links to these settings. Refresh retries the position request.
Windows may return an approximate position: the readout shows reported accuracy
and the map draws an accuracy circle when provided. This is NOT guaranteed GPS.
Stale positions are rejected. No fixed city or silent IP fallback is used.
If no position is available, use the options menu to enter coordinates manually
or explicitly request an approximate IP lookup (with its own permission prompt).
IP lookup may show another city, particularly with a VPN.

GOOGLE MAPS
"Open Google Maps" opens the Google web map inside JARVIS as a separate view.
It is not the screenshot-style HUD. Use its My location button and allow access.
Google's web map cannot provide the exact custom HUD cartography by itself.
A fully custom Google map would require a separately configured Maps JavaScript
API key (a demo key for supported prototype features, or a standard production
key with billing). That custom renderer is NOT included here.
Your Gemini or ElevenLabs key must not be treated as a Maps setup.
https://developers.google.com/maps/documentation/javascript/get-api-key

PRIVACY
Windows supplies device coordinates. OpenStreetMap sees your IP and viewed
map tiles. ipwho.is is contacted only after choosing Approximate IP location.
JARVIS does not save position responses or continuously track you. Map images
may be cached by the embedded browser. Voice/API keys are not sent to these
providers. The separate Google view has its own explicit location permission.

COMPONENTS
Leaflet 1.9.4 (BSD-2-Clause); license bundled in assets/location.
https://leafletjs.com/reference.html
Map data (c) OpenStreetMap contributors, ODbL:
https://www.openstreetmap.org/copyright
https://operations.osmfoundation.org/policies/tiles/
https://ipwhois.io/documentation
https://doc.qt.io/qt-6/qgeopositioninfosource.html

Tests (inside payload):
py -m unittest test_location_map.py test_launcher.py test_google_location.py
