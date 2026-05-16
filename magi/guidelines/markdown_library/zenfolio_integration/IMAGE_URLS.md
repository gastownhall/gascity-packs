# Image URL Construction and Sizing

Zenfolio generates multiple image sizes from the uploaded original. **Selecting the correct image size for each UI context optimizes bandwidth, rendering performance, and user experience.**

### Size Selection

| Size | Dimensions | Use |
|:-----|:----------:|:----|
| Thumbnail | 120 px | Grid cells, navigation |
| Medium | 580 px | Inline previews, search results |
| Large | 800 px | Lightbox, detail views |
| XLarge | 1100 px | Full-screen display |
| XXLarge | 1550 px | Full-screen display (large monitors) |
| Original | Native | **Download only** when the photographer has enabled original downloads |

**Serving originals (often 5000px+ and 10MB+) for grid thumbnails is a bandwidth disaster and a performance violation.**

### URL Construction

Zenfolio image URLs follow a predictable pattern based on the photo's sequence number and size suffix. The Photo object's various URL fields (`ThumbnailUrl`, etc.) provide pre-computed URLs. **Prefer using the URLs returned by the API rather than constructing them** — URL patterns may change between API versions.

### Responsive Image Loading

- In a gallery grid, **load thumbnails first**.
- When the user clicks a photo (lightbox), load the **large or XLarge** version.
- **Preload the next and previous photos** in lightbox navigation for smooth transitions.
- Use `loading="lazy"` or **Intersection Observer** for below-the-fold thumbnails in large galleries.

### Video Content

For video content (`isVideo` flag on the Photo object):

- `OriginalUrl` points to the **highest-quality generated video, not the uploaded original**. Zenfolio does not store original video files.
- Video thumbnails are available via the standard thumbnail URL fields.
- Handle video rendering with a **video player component, not an `img` tag**.

---
[Back to Overview](./OVERVIEW.md)
