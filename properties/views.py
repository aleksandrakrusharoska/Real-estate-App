from decimal import Decimal
import json
import logging

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Max, Min, Q, Sum
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from groq import RateLimitError as GroqRateLimitError

logger = logging.getLogger(__name__)

from properties.forms import PropertyForm
from properties.models import Property, PropertyImage, Feature, TourRequest
from properties.services.ai_chat import (
    call_groq, call_groq_chat, call_groq_prompt, parse_ai_response, is_groq_configured,
    apply_filters, detect_intent, serialize_property_for_comparison,
    build_comparison_prompt,
)

def property_list(request):

    properties = Property.objects.filter(status="approved").prefetch_related("images", "features")

    city = request.GET.get("city", "").strip()
    listing_type = request.GET.get("listing_type")
    property_type = request.GET.get("property_type")
    min_price = request.GET.get("min_price")
    max_price = request.GET.get("max_price")

    price_range = request.GET.get("price_range", "")
    if price_range and not min_price and not max_price:
        if price_range.endswith("+"):
            min_price = price_range[:-1]
        elif "-" in price_range:
            parts = price_range.split("-", 1)
            min_price, max_price = parts[0], parts[1]
    min_area = request.GET.get("min_area")
    min_bedrooms = request.GET.get("bedrooms")
    min_bathrooms = request.GET.get("bathrooms")
    feature_ids = request.GET.getlist("features")
    keyword = request.GET.get("q", "").strip()

    if city:
        properties = properties.filter(city__icontains=city)
    if listing_type:
        properties = properties.filter(listing_type=listing_type)
    if property_type:
        properties = properties.filter(property_type=property_type)
    if min_price:
        properties = properties.filter(price__gte=Decimal(min_price))
    if max_price:
        properties = properties.filter(price__lte=Decimal(max_price))
    if min_area:
        properties = properties.filter(area__gte=Decimal(min_area))
    if min_bedrooms:
        properties = properties.filter(bedrooms__gte=min_bedrooms.rstrip("+"))
    if min_bathrooms:
        properties = properties.filter(bathrooms__gte=min_bathrooms.rstrip("+"))
    if feature_ids:
        properties = properties.filter(features__id__in=feature_ids)
    if keyword:
        properties = properties.filter(
            Q(name__icontains=keyword) |
            Q(description__icontains=keyword) |
            Q(custom_features__icontains=keyword) |
            Q(features__name__icontains=keyword)
        )

    properties = properties.distinct()

    sort_by = request.GET.get('sort', '-created_at')
    allowed_sorts = ['price', '-price', '-created_at']

    if sort_by in allowed_sorts:
        properties = properties.order_by(sort_by)
    else:
        properties = properties.order_by('-created_at')

    paginator = Paginator(properties, 9)
    page_obj = paginator.get_page(request.GET.get('page'))

    base_query = request.GET.copy()
    base_query.pop('page', None)
    base_query_string = base_query.urlencode()

    return render(request, "properties/properties.html", {
        "properties": page_obj,
        "page_obj": page_obj,
        "base_query_string": base_query_string,
        "features": Feature.objects.all(),
        "property_types": Property.PROPERTY_TYPE_CHOICES,
        "selected_listing_type": listing_type,
        "selected_features": feature_ids,
        "selected_property_type": property_type,
        "selected_city": city,
        "selected_keyword": keyword,
        "current_sort": sort_by,
        "featured_properties": Property.objects.filter(status="approved").prefetch_related("images").order_by("-created_at")[:3],
    })

def property_details(request, id):
    property_obj = get_object_or_404(Property, id=id, status="approved")
    if request.method == "POST":
        TourRequest.objects.create(
            property=property_obj,
            name=request.POST.get("name"),
            email=request.POST.get("email"),
            phone=request.POST.get("phone", ""),
            message=request.POST.get("message", "")
        )
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return HttpResponse("OK")
        return redirect("property_details", id=id)
    return render(request, "properties/property_details.html", {"property": property_obj})


@login_required
def create_property(request):
    if request.method == "POST":
        form = PropertyForm(request.POST, request.FILES)
        if form.is_valid():
            property_obj = form.save(commit=False)
            property_obj.owner = request.user
            property_obj.save()
            form.save_m2m()

            images = request.FILES.getlist("images")
            new_cover_index = request.POST.get("new_cover_image")

            for i, img in enumerate(images):
                PropertyImage.objects.create(
                    property=property_obj,
                    image=img,
                    is_cover=(str(i) == str(new_cover_index))
                )

            if property_obj.images.exists() and not property_obj.images.filter(is_cover=True).exists():
                first = property_obj.images.first()
                first.is_cover = True
                first.save()

            return redirect("profile")
    else:
        form = PropertyForm()

    return render(request, "properties/form.html", {
        "form": form
    })


@login_required
def edit_property(request, pk):
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user)

    if request.method == "POST":
        form = PropertyForm(request.POST, request.FILES, instance=property_obj)
        if form.is_valid():
            edited = form.save(commit=False)
            edited.save()
            form.save_m2m()

            images_to_delete = request.POST.getlist("delete_images")
            if images_to_delete:
                PropertyImage.objects.filter(id__in=images_to_delete, property=edited).delete()

            new_images = request.FILES.getlist("images")
            new_cover_index = request.POST.get("new_cover_image")

            created_images = []
            for i, img in enumerate(new_images):
                new_obj = PropertyImage.objects.create(
                    property=edited,
                    image=img,
                    is_cover=(str(i) == str(new_cover_index))
                )
                created_images.append(new_obj)

            selected_cover = request.POST.get("cover_image")

            if selected_cover:
                edited.images.all().update(is_cover=False)
                edited.images.filter(id=selected_cover).update(is_cover=True)
            elif new_cover_index is not None and created_images:
                edited.images.all().update(is_cover=False)
                for i, img_obj in enumerate(created_images):
                    img_obj.is_cover = (str(i) == str(new_cover_index))
                    img_obj.save()

            if edited.images.exists() and not edited.images.filter(is_cover=True).exists():
                first = edited.images.first()
                first.is_cover = True
                first.save()

            return redirect("profile")

    else:
        form = PropertyForm(instance=property_obj)

    return render(request, "properties/form.html", {
        "form": form,
        "property": property_obj
    })


@login_required
def delete_property(request, pk):
    if request.method != "POST":
        return redirect("profile")

    property_obj = get_object_or_404(Property, pk=pk, owner=request.user)
    property_obj.delete()

    return redirect("profile")


def clean_value(value, default="Not provided"):
    return value.strip() if value and value.strip() else default


@login_required
@require_POST
def generate_description(request):
    if not is_groq_configured():
        return JsonResponse({"error": "AI is not configured. Add GROQ_API_KEY to .env and restart the server."}, status=503)

    name = clean_value(request.POST.get("name"))
    property_type = clean_value(request.POST.get("property_type"))
    city = clean_value(request.POST.get("city"))
    location = clean_value(request.POST.get("location"))
    price = clean_value(request.POST.get("price"))
    area = clean_value(request.POST.get("area"))
    rooms = clean_value(request.POST.get("rooms"))
    bedrooms = clean_value(request.POST.get("bedrooms"))
    bathrooms = clean_value(request.POST.get("bathrooms"))
    custom_features = clean_value(request.POST.get("custom_features"), "None")
    ai_prompt = clean_value(request.POST.get("ai_prompt"), "None")

    selected_feature_ids = request.POST.getlist("features")
    selected_features = Feature.objects.filter(id__in=selected_feature_ids)
    features_text = ", ".join(
        selected_features.values_list("name", flat=True)
    ) if selected_features.exists() else "None"

    prompt = f"""
    Write one short real estate description in English.

    Use only these facts:
    Name: {name}
    Type: {property_type}
    City: {city}
    Location: {location}
    Price: {price} EUR
    Area: {area} m²
    Rooms: {rooms}
    Bedrooms: {bedrooms}
    Bathrooms: {bathrooms}
    Features: {features_text}
    Additional features: {custom_features}

    User wishes:
    {ai_prompt}

    Rules:
    - One paragraph only
    - Maximum 3 sentences
    - Simple and factual
    - No headings
    - No bullet points
    - Do not repeat the input
    - Do not add missing details
    - Do not rename or upgrade features

    Return only the final paragraph.
    """

    try:
        description = call_groq_prompt(prompt)
        if not description:
            return JsonResponse({"error": "No response from AI"}, status=500)
        return JsonResponse({"description": description})
    except GroqRateLimitError:
        return JsonResponse({"error": "AI rate limit reached. Please try again in a few minutes."}, status=429)
    except RuntimeError as e:
        return JsonResponse({"error": str(e)}, status=503)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_POST
def ai_chat(request):
    if not is_groq_configured():
        return JsonResponse({
            "message": "AI is not configured. Add GROQ_API_KEY to .env and restart the server.",
            "properties": [],
            "mode": "chat",
        }, status=503)

    try:
        data = json.loads(request.body)
        user_message = data.get("message", "").strip()
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"error": "Invalid request"}, status=400)

    if not user_message:
        return JsonResponse({"error": "Empty message"}, status=400)

    chat_history = request.session.get("chat_history", [])
    chat_history.append({"role": "user", "content": user_message})

    base_queryset = Property.objects.filter(status="approved").prefetch_related("images", "features")
    intent, matched_props = detect_intent(user_message, base_queryset)

    if intent == "compare":
        try:
            props_data = [serialize_property_for_comparison(p) for p in matched_props]
            prompt = build_comparison_prompt(props_data, chat_history)
            ai_message = call_groq_prompt(prompt)
            if not ai_message:
                ai_message = "I couldn't generate a comparison. Please try again."
        except Exception:
            logger.exception("ai_chat comparison failed")
            return JsonResponse({
                "message": "Sorry, I couldn't compare those properties. Please try again.",
                "properties": [],
                "mode": "compare",
            })

        chat_history.append({"role": "assistant", "content": ai_message, "mode": "compare"})
        request.session["chat_history"] = chat_history
        return JsonResponse({"message": ai_message, "properties": [], "mode": "compare"})

    try:
        raw = call_groq(chat_history)
        parsed = parse_ai_response(raw)
        response_mode = parsed.get("mode", "filter")
        conditions = parsed.get("conditions", [])
        sort = parsed.get("sort", [])
        result_limit = parsed.get("limit") or 8
        ai_message = parsed.get("message", "")
    except GroqRateLimitError:
        ai_message = "I've reached my daily request limit. Please try again in a few minutes."
        chat_history.append({"role": "assistant", "content": ai_message, "mode": "chat", "properties": []})
        request.session["chat_history"] = chat_history
        return JsonResponse({"message": ai_message, "properties": [], "mode": "chat"})
    except Exception:
        logger.exception("ai_chat filter failed")
        try:
            ai_message = call_groq_chat(user_message)
        except GroqRateLimitError:
            ai_message = "I've reached my daily request limit. Please try again in a few minutes."
        except Exception:
            ai_message = "I'm not sure how to help with that. Try asking about specific properties, cities, or price ranges."
        chat_history.append({"role": "assistant", "content": ai_message, "mode": "chat", "properties": []})
        request.session["chat_history"] = chat_history
        return JsonResponse({"message": ai_message, "properties": [], "mode": "chat"})

    if response_mode == "chat":
        chat_history.append({
            "role": "assistant",
            "content": ai_message,
            "mode": "chat",
            "properties": [],
        })
        request.session["chat_history"] = chat_history
        return JsonResponse({"message": ai_message, "properties": [], "mode": "chat"})

    if response_mode == "aggregate":
        qs = apply_filters(base_queryset, {"conditions": conditions, "sort": []})
        operation = parsed.get("operation", "avg")
        agg_field = parsed.get("agg_field", "price")
        total = qs.count()

        agg_func_map = {"avg": Avg, "min": Min, "max": Max, "sum": Sum, "count": Count}
        agg_func = agg_func_map.get(operation, Avg)
        result = qs.aggregate(value=agg_func(agg_field))["value"]

        label_map = {
            "price": "price", "area": "area (m²)",
            "bedrooms": "bedrooms", "bathrooms": "bathrooms", "rooms": "rooms",
        }
        field_label = label_map.get(agg_field, agg_field)
        subject = f"{total} propert{'ies' if total != 1 else 'y'}"

        if result is None:
            ai_message = "No properties found matching those criteria."
        elif operation == "count":
            ai_message = f"There {'are' if total != 1 else 'is'} {total} propert{'ies' if total != 1 else 'y'} matching those criteria."
        elif operation == "avg":
            fmt = f"${result:,.0f}" if agg_field == "price" else f"{result:,.1f}"
            ai_message = f"The average {field_label} across {subject} is {fmt}."
        elif operation == "sum":
            fmt = f"${result:,.0f}" if agg_field == "price" else f"{result:,.0f}"
            ai_message = f"The total {field_label} across {subject} is {fmt}."
        elif operation == "min":
            fmt = f"${result:,.0f}" if agg_field == "price" else f"{result:,.1f}"
            ai_message = f"The lowest {field_label} among {subject} is {fmt}."
        elif operation == "max":
            fmt = f"${result:,.0f}" if agg_field == "price" else f"{result:,.1f}"
            ai_message = f"The highest {field_label} among {subject} is {fmt}."

        chat_history.append({"role": "assistant", "content": ai_message, "mode": "chat", "properties": []})
        request.session["chat_history"] = chat_history
        return JsonResponse({"message": ai_message, "properties": [], "mode": "chat"})

    if response_mode == "question":
        prop = apply_filters(base_queryset, {"conditions": conditions, "sort": sort}).first()
        if not prop:
            ai_message = "I couldn't find a property matching that description."
        else:
            attribute = parsed.get("attribute", "general")
            named_features = list(prop.features.values_list("name", flat=True))
            custom = [f.strip() for f in prop.custom_features.split(",") if f.strip()] if prop.custom_features else []
            all_features = named_features + custom

            if attribute == "features":
                prop_context = (
                    f"Property: {prop.name}, City: {prop.city}, "
                    f"Type: {prop.get_property_type_display()}, Price: ${prop.price:,.0f}\n"
                    f"Listed features: {', '.join(all_features) if all_features else 'none'}\n"
                    f"Custom features text: {prop.custom_features or 'none'}"
                )
                try:
                    ai_message = call_groq_chat(
                        f"{prop_context}\n\nUser question: {user_message}\n\n"
                        f"Answer concisely. If the listed features are not amenities (pool, garage, spa, etc.), "
                        f"clarify that and state the property has no listed amenity features."
                    )
                except Exception:
                    if all_features:
                        ai_message = (
                            f"{prop.name} has {len(all_features)} feature"
                            f"{'s' if len(all_features) != 1 else ''}: {', '.join(all_features)}."
                        )
                    else:
                        ai_message = f"{prop.name} has no listed amenity features."
            elif attribute == "area":
                ai_message = f"{prop.name} has an area of {prop.area} m²."
            elif attribute == "bedrooms":
                ai_message = f"{prop.name} has {prop.bedrooms} bedroom{'s' if prop.bedrooms != 1 else ''}."
            elif attribute == "bathrooms":
                ai_message = f"{prop.name} has {prop.bathrooms} bathroom{'s' if prop.bathrooms != 1 else ''}."
            elif attribute == "rooms":
                ai_message = f"{prop.name} has {prop.rooms} room{'s' if prop.rooms != 1 else ''}."
            elif attribute == "price":
                ai_message = f"{prop.name} is priced at ${prop.price:,.0f}."
            elif attribute == "location":
                ai_message = f"{prop.name} is located at {prop.location}, {prop.city}."
            else:
                prop_summary = (
                    f"Name: {prop.name}, City: {prop.city}, Price: ${prop.price:,.0f}, "
                    f"Area: {prop.area} m², Bedrooms: {prop.bedrooms}, Bathrooms: {prop.bathrooms}, "
                    f"Rooms: {prop.rooms}, Features ({len(all_features)}): {', '.join(all_features) or 'none'}."
                )
                try:
                    ai_message = call_groq_chat(
                        f"Property data: {prop_summary}\n\nUser question: {user_message}\n\nAnswer concisely."
                    )
                except Exception:
                    ai_message = prop_summary

        chat_history.append({"role": "assistant", "content": ai_message, "mode": "chat", "properties": []})
        request.session["chat_history"] = chat_history
        return JsonResponse({"message": ai_message, "properties": [], "mode": "chat"})

    properties = apply_filters(base_queryset, {"conditions": conditions, "sort": sort})
    property_data = []
    for prop in properties[:result_limit]:
        cover = prop.cover_image()
        property_data.append({
            "id": prop.id,
            "name": prop.name,
            "city": prop.city,
            "price": str(prop.price),
            "property_type": prop.get_property_type_display(),
            "listing_type": prop.get_listing_type_display(),
            "listing_type_raw": prop.listing_type,
            "bedrooms": prop.bedrooms,
            "bathrooms": prop.bathrooms,
            "area": str(prop.area),
            "cover_image_url": cover.image.url if cover else None,
            "detail_url": f"/properties/{prop.id}/",
        })

    chat_history.append({
        "role": "assistant",
        "content": ai_message,
        "mode": "filter",
        "properties": property_data,
    })
    request.session["chat_history"] = chat_history
    return JsonResponse({"message": ai_message, "properties": property_data, "mode": "filter"})


def ai_chat_history(request):
    history = request.session.get("chat_history", [])
    return JsonResponse({"messages": history})


@require_POST
def ai_chat_clear(request):
    request.session.pop("chat_history", None)
    return JsonResponse({"status": "cleared"})
