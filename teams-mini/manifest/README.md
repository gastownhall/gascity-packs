# Teams app package

Teams installs a bot from a zip containing `manifest.json` plus the two icons.
The manifest here has `${TEAMS_APP_ID}` where the Azure Bot's Microsoft App ID
goes. Build the package with:

```sh
TEAMS_APP_ID=11111111-2222-3333-4444-555555555555
sed "s/\${TEAMS_APP_ID}/$TEAMS_APP_ID/g" manifest.json > /tmp/manifest.json
zip -j /tmp/teams-mini.zip /tmp/manifest.json color.png outline.png
```

Then in Teams: **Apps → Manage your apps → Upload an app → Upload a custom
app**, pick the zip, and add it to a team, a group chat, or yourself. Your
tenant must allow custom app upload (Teams admin center → Teams apps → Setup
policies). If it does not, a Teams administrator can publish the same zip to
the organisation's app catalogue instead.

The icons are placeholders (solid colour) so the package validates; replace
them with your own 192×192 colour and 32×32 outline PNGs if you like.
