import json
import re
import os
from django.db.models import Q
from decouple import config
from groq import Groq

GROQ_API_KEY = config("GROQ_API_KEY", default=os.getenv("GROQ_API_KEY", "")).strip()
GROQ_MODEL = config("GROQ_MODEL", default="llama-3.3-70b-versatile").strip() or "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """
You are a real estate assistant. Convert the user's message into structured JSON.

Choose one of two modes:

--- MODE: filter ---
Use when the user wants to find, browse, or sort properties.
{
  "mode": "filter",
  "conditions": [
    {"field": "...", "op": "...", "value": ...}
  ],
  "sort": [
    {"field": "...", "direction": "asc" | "desc"}
  ],
  "limit": null,
  "message": "One sentence summary of the search."
}

FIELDS: price, area, rooms, bedrooms, bathrooms, city, location, property_type, listing_type, features
OPS: eq, lt, lte, gt, gte, icontains
SORT fields: price, area, rooms, bedrooms, bathrooms, created_at

Rules:
- "highest price" / "most expensive" → sort: [{"field":"price","direction":"desc"}]
- "lowest price" / "cheapest" → sort: [{"field":"price","direction":"asc"}]
- "less than X bedrooms" → {"field":"bedrooms","op":"lt","value":X}
- "more than X bedrooms" / "at least X bedrooms" → {"field":"bedrooms","op":"gte","value":X}
- "under $X" / "below $X" / "max $X" → {"field":"price","op":"lte","value":X}
- "over $X" / "above $X" / "at least $X" → {"field":"price","op":"gte","value":X}
- "apartments" / "apartment" → {"field":"property_type","op":"eq","value":"apartment"}
- "houses" / "house" → {"field":"property_type","op":"eq","value":"house"}
- "villas" / "villa" → {"field":"property_type","op":"eq","value":"villa"}
- "studios" / "studio" → {"field":"property_type","op":"eq","value":"studio"}
- "land" → {"field":"property_type","op":"eq","value":"land"}
- "commercial" → {"field":"property_type","op":"eq","value":"commercial"}
- "for rent" / "to rent" → {"field":"listing_type","op":"eq","value":"rent"}
- "for sale" / "to buy" → {"field":"listing_type","op":"eq","value":"sale"}
- "in Chicago" → {"field":"city","op":"icontains","value":"Chicago"}
- "not in Chicago" / "outside Chicago" / "excluding Chicago" → {"field":"city","op":"not_icontains","value":"Chicago"}
- "not apartments" / "excluding apartments" → {"field":"property_type","op":"neq","value":"apartment"}
- "not for rent" / "excluding rentals" → {"field":"listing_type","op":"neq","value":"rent"}
- "apartments or houses" → {"field":"property_type","op":"in","value":["apartment","house"]}
- "for rent or for sale" → {"field":"listing_type","op":"in","value":["rent","sale"]}
- "with pool" → {"field":"features","op":"icontains","value":"pool"}
- "with pool AND garage" (both required) → two separate conditions: {"field":"features","op":"icontains","value":"pool"} AND {"field":"features","op":"icontains","value":"garage"}
- "with pool OR garage" (either is enough) → {"field":"features","op":"any_of","value":["pool","garage"]}
- "without pool" / "no pool" / "excluding pool" → {"field":"features","op":"none_of","value":["pool"]}
- "without pool or garage" / "no pool and no garage" → {"field":"features","op":"none_of","value":["pool","garage"]}
- "biggest" / "largest" → sort: [{"field":"area","direction":"desc"}]
- "smallest" → sort: [{"field":"area","direction":"asc"}]
- "newest" / "latest" → sort: [{"field":"created_at","direction":"desc"}]
- "more than X rooms" → {"field":"rooms","op":"gt","value":X}
- "most bathrooms" / "most bedrooms" / "most rooms" → sort by that field desc
- "one property" / "only one" / "show me one" / "top 1" → limit: 1
- "property with most X" → limit: 1 (e.g. "property with most bathrooms" → limit:1, sort bathrooms desc)
- "property with highest X" → limit: 1 (e.g. "property with highest price" → limit:1, sort price desc)
- "property with lowest X" → limit: 1 (e.g. "property with lowest price" → limit:1, sort price asc)
- "cheapest property" / "most expensive property" → limit: 1
- "biggest property" / "largest property" / "smallest property" → limit: 1
- "newest property" / "oldest property" → limit: 1
- plural "properties" → do NOT set limit (leave null)
- "top X" / "show me X" / "X properties" (where X is a small number like 2,3,4,5) → limit: X
- Each user message is a FRESH, independent search. Do NOT carry over conditions from previous messages.
- Use empty arrays [] if no filter or sort criteria are mentioned.
- Use null for limit when no specific count is requested.

--- MODE: aggregate ---
Use when the user asks for a statistic across multiple properties (average, total, minimum, maximum, count).
{
  "mode": "aggregate",
  "conditions": [...],
  "operation": "avg" | "min" | "max" | "sum" | "count",
  "field": "price" | "area" | "bedrooms" | "bathrooms" | "rooms"
}

Examples:
- "average price of houses" → conditions: [property_type=house], operation: "avg", field: "price"
- "how many villas are there?" → conditions: [property_type=villa], operation: "count", field: "price"
- "total value of all properties" → conditions: [], operation: "sum", field: "price"
- "maximum area among apartments" → conditions: [property_type=apartment], operation: "max", field: "area"
- "minimum price in Chicago" → conditions: [city=Chicago], operation: "min", field: "price"

--- MODE: question ---
Use when the user asks a specific factual question about a particular property
(e.g. "how many features does X have?", "what is the area of Y?", "does Z have a pool?", "how many rooms does the house in Chicago have?").
{
  "mode": "question",
  "conditions": [...],
  "sort": [...],
  "attribute": "features" | "area" | "bedrooms" | "bathrooms" | "rooms" | "price" | "location" | "general"
}
Use sort to identify the right property when the user says "most expensive", "cheapest", "biggest", etc.
Example: "how many bathrooms does the most expensive villa have?" →
  conditions: [{"field":"property_type","op":"eq","value":"villa"}], sort: [{"field":"price","direction":"desc"}], attribute: "bathrooms"

attribute values:
- "features" → user asks about features (count, list, or whether it has a specific one)
- "area" → user asks about size/area
- "bedrooms" → user asks about bedrooms
- "bathrooms" → user asks about bathrooms
- "rooms" → user asks about rooms
- "price" → user asks about price
- "location" → user asks about address/city/location
- "general" → any other factual question about the property

--- MODE: chat ---
Use for greetings, general real estate questions, advice, or anything NOT a property search or specific property question.
{
  "mode": "chat",
  "message": "Your helpful, conversational response here."
}

Return ONLY valid JSON. No markdown, no extra text.
"""


def build_prompt(chat_history):
    conversation = "\n".join(
        f"{msg.get('role','user').upper()}: {msg.get('content','')}"
        for msg in chat_history
    )
    return f"{SYSTEM_PROMPT}\n\nConversation:\n{conversation}\n\nJSON:"


def is_groq_configured():
    return bool(GROQ_API_KEY)


def get_groq_client():
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing. Add it to .env and restart the server.")
    return Groq(api_key=GROQ_API_KEY)


def call_groq_prompt(prompt):
    """Single-turn prompt — used for description generation and property comparison."""
    client = get_groq_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


def call_groq(chat_history):
    client = get_groq_client()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in chat_history:
        role = msg.get("role", "user")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": msg.get("content", "")})
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def call_groq_chat(user_message):
    client = get_groq_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful real estate assistant. Answer the user's question naturally and concisely."},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


def safe_num(value):
    try:
        if value is None:
            return None
        s = str(value).replace(",", "").strip()
        f = float(s)
        return int(f) if f == int(f) else f
    except Exception:
        return None


ALLOWED_FIELDS = {
    "price", "area", "rooms", "bedrooms", "bathrooms",
    "city", "location", "property_type", "listing_type", "features",
}
ALLOWED_OPS = {"eq", "lt", "lte", "gt", "gte", "icontains", "any_of", "neq", "not_icontains", "in", "none_of"}
ALLOWED_SORT_FIELDS = {"price", "area", "rooms", "bedrooms", "bathrooms", "created_at"}
ALLOWED_DIRECTIONS = {"asc", "desc"}

FIELD_LOOKUPS = {
    "eq": "",
    "lt": "__lt",
    "lte": "__lte",
    "gt": "__gt",
    "gte": "__gte",
    "icontains": "__icontains",
}

NUMERIC_FIELDS = {"price", "area", "rooms", "bedrooms", "bathrooms"}


def validate_condition(cond):
    if not isinstance(cond, dict):
        return None
    field = cond.get("field")
    op = cond.get("op", "eq")
    value = cond.get("value")
    if field not in ALLOWED_FIELDS or op not in ALLOWED_OPS or value is None:
        return None
    if op in ("any_of", "none_of"):
        if field != "features" or not isinstance(value, list) or not value:
            return None
        return {"field": field, "op": op, "value": [str(v) for v in value]}
    if op == "in":
        if not isinstance(value, list) or not value:
            return None
        if field in NUMERIC_FIELDS:
            value = [safe_num(v) for v in value]
            if any(v is None for v in value):
                return None
        return {"field": field, "op": op, "value": value}
    if field in ("city", "location") and op == "eq":
        op = "icontains"
    if field in NUMERIC_FIELDS:
        value = safe_num(value)
        if value is None:
            return None
    return {"field": field, "op": op, "value": value}


def validate_sort(s):
    if not isinstance(s, dict):
        return None
    field = s.get("field")
    direction = s.get("direction", "asc")
    if field not in ALLOWED_SORT_FIELDS or direction not in ALLOWED_DIRECTIONS:
        return None
    return {"field": field, "direction": direction}


def build_message_from_conditions(conditions, sort):
    parts = ["Properties"]

    for cond in conditions:
        field = cond.get("field")
        op = cond.get("op")
        value = cond.get("value")

        if field == "city":
            parts.append(f"in {value}")
        elif field == "property_type":
            parts[0] = str(value).capitalize() + "s"
        elif field == "listing_type":
            parts.append("for rent" if value == "rent" else "for sale")
        elif field == "price":
            if op in ("lte", "lt"):
                parts.append(f"under ${int(value):,}")
            elif op in ("gte", "gt"):
                parts.append(f"over ${int(value):,}")
        elif field == "bedrooms":
            if op in ("gte", "gt"):
                parts.append(f"with {value}+ bedrooms")
            elif op in ("lte", "lt"):
                parts.append(f"with fewer than {value} bedrooms")
            elif op == "eq":
                parts.append(f"with {value} bedrooms")
        elif field == "bathrooms":
            if op in ("gte", "gt"):
                parts.append(f"with {value}+ bathrooms")
            elif op in ("lte", "lt"):
                parts.append(f"with fewer than {value} bathrooms")
            elif op == "eq":
                parts.append(f"with {value} bathrooms")
        elif field == "area":
            if op in ("gte", "gt"):
                parts.append(f"over {value}m²")
            elif op in ("lte", "lt"):
                parts.append(f"under {value}m²")
        elif field == "rooms":
            if op in ("gte", "gt"):
                parts.append(f"with {value}+ rooms")
            elif op in ("lte", "lt"):
                parts.append(f"with fewer than {value} rooms")
        elif field == "features":
            parts.append(f"with {value}")
        elif field == "location":
            parts.append(f"near {value}")

    for s in sort:
        field = s.get("field")
        direction = s.get("direction")
        if field == "price":
            parts.append("(highest price first)" if direction == "desc" else "(lowest price first)")
        elif field == "area":
            parts.append("(largest first)" if direction == "desc" else "(smallest first)")
        elif field == "created_at":
            parts.append("(newest first)")
        elif field == "bedrooms":
            parts.append("(most bedrooms first)" if direction == "desc" else "(fewest bedrooms first)")

    return " ".join(parts) + "."


def parse_ai_response(raw):
    text = raw.strip()

    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                text = part
                break

    start = text.find("{")
    end = text.rfind("}") + 1

    if start == -1 or end == 0:
        raise ValueError("No JSON found")

    parsed = json.loads(text[start:end])
    mode = parsed.get("mode", "filter")

    if mode == "chat":
        return {
            "mode": "chat",
            "message": parsed.get("message", "How can I help you?"),
            "conditions": [],
            "sort": [],
        }

    if mode == "aggregate":
        raw_conditions = parsed.get("conditions", [])
        conditions = [c for c in (validate_condition(c) for c in raw_conditions) if c]
        allowed_ops = {"avg", "min", "max", "sum", "count"}
        allowed_fields = {"price", "area", "bedrooms", "bathrooms", "rooms"}
        operation = parsed.get("operation", "avg")
        agg_field = parsed.get("field", "price")
        if operation not in allowed_ops:
            operation = "avg"
        if agg_field not in allowed_fields:
            agg_field = "price"
        return {
            "mode": "aggregate",
            "conditions": conditions,
            "operation": operation,
            "agg_field": agg_field,
            "sort": [],
            "limit": None,
            "message": "",
        }

    if mode == "question":
        raw_conditions = parsed.get("conditions", [])
        raw_sort = parsed.get("sort", [])
        conditions = [c for c in (validate_condition(c) for c in raw_conditions) if c]
        sort = [s for s in (validate_sort(s) for s in raw_sort) if s]
        allowed_attrs = {"features", "area", "bedrooms", "bathrooms", "rooms", "price", "location", "general"}
        attribute = parsed.get("attribute", "general")
        if attribute not in allowed_attrs:
            attribute = "general"
        return {
            "mode": "question",
            "conditions": conditions,
            "attribute": attribute,
            "sort": sort,
            "limit": 1,
            "message": "",
        }

    raw_conditions = parsed.get("conditions", [])
    raw_sort = parsed.get("sort", [])

    conditions = [c for c in (validate_condition(c) for c in raw_conditions) if c]
    sort = [s for s in (validate_sort(s) for s in raw_sort) if s]

    raw_limit = parsed.get("limit")
    try:
        limit = int(raw_limit) if raw_limit is not None else None
        if limit is not None and limit < 1:
            limit = None
    except (TypeError, ValueError):
        limit = None

    message = parsed.get("message") or build_message_from_conditions(conditions, sort)

    return {
        "mode": "filter",
        "conditions": conditions,
        "sort": sort,
        "limit": limit,
        "message": message,
    }


def apply_filters(queryset, parsed):
    conditions = parsed.get("conditions", [])
    sort = parsed.get("sort", [])

    for cond in conditions:
        field = cond["field"]
        op = cond["op"]
        value = cond["value"]

        if field == "features" and op == "any_of":
            q = Q()
            for v in value:
                q |= Q(features__name__icontains=v) | Q(custom_features__icontains=v)
            queryset = queryset.filter(q).distinct()
            continue

        if field == "features" and op == "none_of":
            for v in value:
                queryset = queryset.exclude(
                    Q(features__name__icontains=v) | Q(custom_features__icontains=v)
                )
            queryset = queryset.distinct()
            continue

        if field == "features":
            queryset = queryset.filter(
                Q(features__name__icontains=value) |
                Q(custom_features__icontains=value)
            ).distinct()
            continue

        if op == "neq":
            queryset = queryset.exclude(**{field: value})
            continue

        if op == "not_icontains":
            queryset = queryset.exclude(**{f"{field}__icontains": value})
            continue

        if op == "in":
            queryset = queryset.filter(**{f"{field}__in": value})
            continue

        suffix = FIELD_LOOKUPS.get(op, "")
        lookup = f"{field}{suffix}" if suffix else field
        queryset = queryset.filter(**{lookup: value})

    if sort:
        order_fields = []
        for s in sort:
            prefix = "-" if s["direction"] == "desc" else ""
            order_fields.append(f"{prefix}{s['field']}")
        queryset = queryset.order_by(*order_fields)

    return queryset


COMPARISON_SYSTEM_PROMPT = """You are a helpful real estate assistant.
Compare the properties using exactly this format:

**[Property 1 name] vs [Property 2 name]**

• **Price:** $X vs $Y
• **Price/m²:** $X vs $Y
• **Size:** Xm² vs Ym²
• **Beds/Baths:** X bed X bath vs Y bed Y bath
• **Location:** City1 vs City2

**Verdict:** One sentence saying which is the better deal and why.

Only use the provided data. No extra lines or commentary."""


def detect_intent(message, queryset):
    found = []
    seen_ids = set()

    id_matches = re.findall(
        r'(?:#|(?:property|id|listing)\s+)(\d+)', message, re.IGNORECASE
    )
    for id_str in id_matches:
        try:
            prop = queryset.filter(id=int(id_str)).first()
            if prop and prop.id not in seen_ids:
                found.append(prop)
                seen_ids.add(prop.id)
        except (ValueError, TypeError):
            pass

    if len(found) < 2:
        for prop in queryset:
            if prop.id in seen_ids or len(prop.name) < 4:
                continue
            if re.search(r'\b' + re.escape(prop.name) + r'\b', message, re.IGNORECASE):
                found.append(prop)
                seen_ids.add(prop.id)
            if len(found) >= 4:
                break

    if len(found) >= 2:
        return ("compare", found[:4])
    return ("filter", [])


def serialize_property_for_comparison(prop):
    features = list(prop.features.values_list('name', flat=True))
    price_per_m2 = (
        round(float(prop.price) / float(prop.area), 2) if prop.area else None
    )
    return {
        "id": prop.id,
        "name": prop.name,
        "city": prop.city,
        "location": prop.location,
        "price": float(prop.price),
        "area": float(prop.area),
        "price_per_m2": price_per_m2,
        "property_type": prop.get_property_type_display(),
        "listing_type": prop.get_listing_type_display(),
        "bedrooms": prop.bedrooms,
        "bathrooms": prop.bathrooms,
        "rooms": prop.rooms,
        "features": features,
        "custom_features": prop.custom_features or "",
    }


def build_comparison_prompt(props_data, chat_history):
    props_text = "\n\n".join(
        "Property {n}: {name} (ID: {id})\n"
        "  City: {city}, Location: {location}\n"
        "  Price: ${price:,.0f} ({listing_type})\n"
        "  Price per m²: ${price_per_m2}\n"
        "  Type: {property_type}, Area: {area} m²\n"
        "  Bedrooms: {bedrooms}, Bathrooms: {bathrooms}\n"
        "  Features: {features}\n"
        "  Additional: {custom_features}".format(
            n=i + 1,
            features=", ".join(p["features"]) or "None",
            **{k: v for k, v in p.items() if k != "features"},
        )
        for i, p in enumerate(props_data)
    )
    last_user_msg = next(
        (m["content"] for m in reversed(chat_history) if m["role"] == "user"),
        "Which is better?",
    )
    return (
        f"{COMPARISON_SYSTEM_PROMPT}\n\n"
        f"Properties:\n{props_text}\n\n"
        f"User question: {last_user_msg}\n\nYour comparison:"
    )
