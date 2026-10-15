"""HTML Visual Showcase Generator for ChronoCull (Phase 2, Component 5)."""

import html
import os
from pathlib import Path

from chronocull.core.clustering import TripClusterResult


def _generate_css() -> str:
    """Return inline CSS for the responsive editorial layout."""
    return """
    :root {
        --bg: #fdfbf7;
        --text: #2c2c2c;
        --accent: #d35400;
        --border: #e6e0d4;
    }
    body {
        font-family: 'Georgia', serif;
        background-color: var(--bg);
        color: var(--text);
        line-height: 1.6;
        margin: 0;
        padding: 0;
    }
    header {
        text-align: center;
        padding: 4rem 1rem;
        border-bottom: 1px solid var(--border);
        background-color: #f4f0e6;
    }
    header h1 {
        font-size: 3rem;
        margin: 0 0 0.5rem 0;
        font-weight: normal;
        letter-spacing: -0.02em;
    }
    header p {
        font-family: 'Helvetica Neue', sans-serif;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        font-size: 0.9rem;
    }
    main {
        max-width: 900px;
        margin: 0 auto;
        padding: 2rem 1rem;
    }
    .day-section {
        margin-bottom: 5rem;
    }
    .day-header {
        font-size: 2rem;
        border-bottom: 2px solid var(--text);
        padding-bottom: 0.5rem;
        margin-bottom: 2rem;
        font-weight: normal;
    }
    .stop-card {
        margin-bottom: 4rem;
    }
    .stop-header {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 1rem;
    }
    .stop-title {
        font-size: 1.5rem;
        margin: 0;
        color: var(--accent);
    }
    .stop-meta {
        font-family: 'Helvetica Neue', sans-serif;
        font-size: 0.85rem;
        color: #777;
    }
    .apify-context {
        background-color: #fff;
        padding: 1rem;
        border-left: 3px solid var(--accent);
        font-style: italic;
        margin-bottom: 1.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .photo-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 1.5rem;
    }
    .photo-item {
        display: flex;
        flex-direction: column;
    }
    .photo-item img {
        width: 100%;
        height: auto;
        border-radius: 2px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        display: block;
    }
    .caption {
        font-family: 'Helvetica Neue', sans-serif;
        font-size: 0.85rem;
        color: #555;
        margin-top: 0.75rem;
    }
    .tags {
        font-size: 0.75rem;
        color: #999;
        margin-top: 0.25rem;
        text-transform: uppercase;
    }
    footer {
        text-align: center;
        padding: 3rem;
        font-family: 'Helvetica Neue', sans-serif;
        font-size: 0.8rem;
        color: #999;
        border-top: 1px solid var(--border);
    }
    @media (max-width: 600px) {
        header h1 { font-size: 2rem; }
        .stop-header { flex-direction: column; }
    }
    """


def generate_html_showcase(cluster_result: TripClusterResult, folder_path: Path) -> Path:
    """Generate a responsive HTML travelogue album for the trip."""
    
    html_parts = []
    
    # DOCTYPE and Head
    html_parts.append("<!DOCTYPE html>")
    html_parts.append("<html lang='en'>")
    html_parts.append("<head>")
    html_parts.append("  <meta charset='UTF-8'>")
    html_parts.append("  <meta name='viewport' content='width=device-width, initial-scale=1.0'>")
    trip_title = f"Trip Album: {folder_path.name}"
    html_parts.append(f"  <title>{html.escape(trip_title)}</title>")
    html_parts.append(f"  <style>{_generate_css()}</style>")
    html_parts.append("</head>")
    html_parts.append("<body>")
    
    # Header
    html_parts.append("<header>")
    html_parts.append(f"  <h1>{html.escape(folder_path.name)}</h1>")
    html_parts.append(f"  <p>{len(cluster_result.days)} Days • {cluster_result.total_stops} Stops • {cluster_result.total_items} Memories</p>")
    html_parts.append("</header>")
    
    # Main Content
    html_parts.append("<main>")
    
    for day in cluster_result.days:
        html_parts.append("  <section class='day-section'>")
        html_parts.append(f"    <h2 class='day-header'>Day {day.day_number} &mdash; {html.escape(day.date)}</h2>")
        
        for stop in day.stops:
            html_parts.append("    <div class='stop-card'>")
            
            # Stop Header
            time_str = f"{stop.start_time.strftime('%I:%M %p').lstrip('0')} - {stop.end_time.strftime('%I:%M %p').lstrip('0')}"
            loc_str = stop.location.get("city") or "Unknown Location"
            
            html_parts.append("      <div class='stop-header'>")
            html_parts.append(f"        <h3 class='stop-title'>{html.escape(stop.title)}</h3>")
            html_parts.append(f"        <div class='stop-meta'>📍 {html.escape(loc_str)} • 🕒 {time_str}</div>")
            html_parts.append("      </div>")
            
            # Apify Context (if available)
            if stop.apify_context and stop.apify_context.get("description"):
                desc = stop.apify_context["description"]
                rating = stop.apify_context.get("rating", "")
                rating_str = f" (★ {rating})" if rating else ""
                html_parts.append(f"      <div class='apify-context'>\n        {html.escape(desc)}{rating_str}\n      </div>")
            
            # Photos
            html_parts.append("      <div class='photo-grid'>")
            
            # Prioritize hero images or fallback to up to 4 standard images
            heroes = [it for it in stop.items if it.media_type == "image" and it.metadata.get("is_hero_candidate", False)]
            if not heroes:
                heroes = [it for it in stop.items if it.media_type == "image"][:4]
                
            for item in heroes:
                # Relative path from the html file to the image
                proposed_name = item.proposed_name or item.original_name
                if (folder_path / proposed_name).exists():
                    img_src = html.escape(proposed_name)
                elif item.target_path and item.target_path.exists():
                    try:
                        rel = os.path.relpath(item.target_path, folder_path)
                        img_src = html.escape(rel)
                    except ValueError:
                        img_src = html.escape(str(item.target_path))
                else:
                    try:
                        rel = os.path.relpath(item.original_path, folder_path)
                        img_src = html.escape(rel)
                    except ValueError:
                        img_src = html.escape(str(item.original_path))
                
                html_parts.append("        <div class='photo-item'>")
                html_parts.append(f"          <img src='{img_src}' alt='{html.escape(item.original_name)}' loading='lazy'>")
                
                # Check for AI Curation metadata
                ai_data = item.metadata.get("ai_curation", {})
                if ai_data:
                    caption = ai_data.get("caption", "")
                    tags = " • ".join(ai_data.get("tags", []))
                    if caption:
                        html_parts.append(f"          <div class='caption'>{html.escape(caption)}</div>")
                    if tags:
                        html_parts.append(f"          <div class='tags'>{html.escape(tags)}</div>")
                        
                html_parts.append("        </div>")
                
            html_parts.append("      </div>") # end photo-grid
            html_parts.append("    </div>") # end stop-card
            
        html_parts.append("  </section>") # end day-section
        
    html_parts.append("</main>")
    html_parts.append("<footer>")
    html_parts.append("  Generated by <a href='https://github.com/nandappamn/ChronoCull' style='color:inherit;'>ChronoCull Media Curation Engine</a>")
    html_parts.append("</footer>")
    html_parts.append("</body>")
    html_parts.append("</html>")
    
    out_path = folder_path / "travel_album.html"
    out_path.write_text("\n".join(html_parts), encoding="utf-8")
    return out_path

