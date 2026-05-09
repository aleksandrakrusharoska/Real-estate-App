import requests
import time
import random
from decouple import config
from django.core.management.base import BaseCommand
from properties.models import Property, PropertyImage, Feature
from django.contrib.auth.models import User
from django.core.files.base import ContentFile


class Command(BaseCommand):
    help = 'Final Fetch: Real coordinates, m2 conversion, and auto-amenities'

    def handle(self, *args, **kwargs):
        api_key = config('RAPIDAPI_KEY')
        host = "realtor16.p.rapidapi.com"
        headers = {"x-rapidapi-key": api_key, "x-rapidapi-host": host}

        all_users = list(User.objects.all())
        admin_user = User.objects.filter(is_superuser=True).first()

        random_cities = ["miami, fl", "los angeles, ca", "chicago, il", "austin, tx", "las vegas, nv"]
        selected_cities = random.sample(random_cities, 2)

        endpoints = [
            ("https://realtor16.p.rapidapi.com/search/forsale", "sale"),
            ("https://realtor16.p.rapidapi.com/search/forrent", "rent")
        ]

        for city in selected_cities:
            for url, listing_type in endpoints:
                self.stdout.write(self.style.SUCCESS(f"\n--- Fetching {listing_type.upper()} in {city.upper()} ---"))

                params = {"location": city, "limit": "5"}
                time.sleep(1)

                try:
                    response = requests.get(url, headers=headers, params=params)
                    if response.status_code == 200:
                        properties_list = response.json().get('properties', [])

                        for item in properties_list:
                            desc_data = item.get('description', {})
                            loc_data = item.get('location', {})
                            addr = loc_data.get('address', {})
                            p_address = addr.get('line', 'Unknown Address')

                            raw_sqft = desc_data.get('sqft', 0) or 0
                            area_m2 = int(raw_sqft * 0.0929) if raw_sqft > 0 else random.randint(40, 150)

                            coords = addr.get('coordinate', {})
                            lat = coords.get('lat')
                            lon = coords.get('lon')

                            api_description = desc_data.get('text', "").strip()
                            if not api_description:
                                api_description = f"Beautiful {desc_data.get('type', 'property')} located in the heart of {city}. Modern design with great amenities."

                            assigned_owner = random.choice(all_users) if all_users else admin_user

                            prop = Property.objects.create(
                                name=p_address,
                                owner=assigned_owner,
                                listing_type=listing_type,
                                price=item.get('list_price', 0) or item.get('estimate', {}).get('value',
                                                                                                0) or random.randint(
                                    150000, 500000),
                                city=addr.get('city', city.split(',')[0].title()),
                                location=p_address,
                                area=area_m2,
                                rooms=desc_data.get('beds', 0) or 0,
                                bedrooms=desc_data.get('beds', 0) or 0,
                                bathrooms=int(float(str(desc_data.get('baths_consolidated', 0) or 0).replace('+', ''))),
                                latitude=lat,
                                longitude=lon,
                                status='approved',
                                description=api_description,
                                property_type=desc_data.get('type', 'house').lower()
                            )

                            flags = item.get('flags', {})
                            added_features = []
                            for flag_name, has_it in flags.items():
                                if has_it is True:
                                    clean_name = flag_name.replace('_', ' ').title()
                                    feature_obj, _ = Feature.objects.get_or_create(name=clean_name)
                                    prop.features.add(feature_obj)
                                    added_features.append(clean_name)

                            self.stdout.write(f"Successful!")

                            photos = item.get('photos', [])[:5]
                            for index, photo in enumerate(photos):
                                raw_url = photo.get('href')
                                if raw_url:
                                    hd_url = raw_url.replace("s.jpg", "rd.jpg").replace("m.jpg", "rd.jpg")
                                    try:
                                        img_res = requests.get(hd_url, timeout=10)
                                        if img_res.status_code == 200:
                                            new_img = PropertyImage(property=prop, is_cover=(index == 0))
                                            new_img.image.save(f"prop_{prop.id}_{index}.jpg",
                                                               ContentFile(img_res.content), save=True)
                                    except Exception:
                                        continue
                    else:
                        self.stdout.write(self.style.ERROR(f"API error: {response.status_code}"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Critical Error: {e}"))

        self.stdout.write(self.style.SUCCESS("\nDone!"))