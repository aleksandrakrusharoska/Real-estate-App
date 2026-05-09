import re
from django import template
from django.utils.html import mark_safe, conditional_escape

register = template.Library()

SECTION_ICONS = {
    "curb": "bi-house-heart",
    "kitchen": "bi-tools",
    "bathroom": "bi-tools",
    "energy": "bi-thermometer-sun",
    "declutter": "bi-stars",
    "stage": "bi-stars",
    "fix": "bi-hammer",
    "school": "bi-mortarboard",
    "safety": "bi-shield-check",
    "green": "bi-tree-fill",
    "convenience": "bi-signpost-2",
    "growth": "bi-graph-up-arrow",
    "investment": "bi-bullseye",
    "goal": "bi-bullseye",
    "numbers": "bi-calculator",
    "location": "bi-geo-alt",
    "financing": "bi-bank",
    "team": "bi-people",
    "biophilic": "bi-tree",
    "net-zero": "bi-lightning-charge",
    "flexible": "bi-grid-1x2",
    "modular": "bi-boxes",
    "smart": "bi-cpu",
}

DEFAULT_ICONS = [
    "bi-star", "bi-check-circle", "bi-arrow-right-circle",
    "bi-bookmark", "bi-lightbulb", "bi-gem",
]


def _pick_icon(title, index):
    title_lower = title.lower()
    for keyword, icon in SECTION_ICONS.items():
        if keyword in title_lower:
            return icon
    return DEFAULT_ICONS[index % len(DEFAULT_ICONS)]


@register.filter(name="format_blog", is_safe=True)
def format_blog(content):
    """Parse plain-text blog content into structured HTML sections."""
    if not content:
        return ""

    
    if content.strip().startswith("<"):
        return mark_safe(content)

    paragraphs = [p.strip() for p in re.split(r"\r?\n\r?\n", content) if p.strip()]
    if not paragraphs:
        return ""

    html_parts = []

    
    html_parts.append(f'<p class="lead mb-4">{conditional_escape(paragraphs[0])}</p>')

    for i, para in enumerate(paragraphs[1:]):
        match = re.match(r"^(.+?)\s[—–-]\s(.+)$", para, re.DOTALL)
        if match:
            title = match.group(1).strip()
            body = match.group(2).strip()
            icon = _pick_icon(title, i)
            html_parts.append(
                f'<div class="blog-section">'
                f'<div class="blog-section-icon"><i class="bi {icon}"></i></div>'
                f'<div><h5>{conditional_escape(title)}</h5><p>{conditional_escape(body)}</p></div>'
                f'</div>'
            )
        else:
            html_parts.append(f"<p>{conditional_escape(para)}</p>")

    return mark_safe("\n".join(html_parts))
