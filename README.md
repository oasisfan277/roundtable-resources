# The RoundTable Resources Website

This is a static website generated from the sibling `resources` folder.

The site is designed for GitHub Pages and can also be tested locally with any simple web server. External shortcut files become normal web links, while PDF, Word, RTF, text, and other local files are copied into `downloads` and linked as downloads.

Every folder in `resources` gets its own generated page under `categories`. For example, the French folder becomes a French category page containing the resources from that folder.

Search forms submit to `search.html`, which renders results from the generated `assets/search-data.js` index.

To rebuild after changing the resources folder and publish the live GitHub Pages site:

```powershell
python .\tools\build_site.py
```

That command rebuilds the local files, commits the website changes, and pushes `main` to `origin`.

To rebuild locally without publishing:

```powershell
python .\tools\build_site.py --local-only
```

To use a custom commit message:

```powershell
python .\tools\build_site.py --message "Update RoundTable resources"
```
