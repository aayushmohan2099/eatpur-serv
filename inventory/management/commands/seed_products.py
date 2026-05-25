# inventory/management/commands/seed_products.py

from django.core.management.base import BaseCommand
from inventory.models import (
    Product,
    ProductCategory,
    ProductMedia,
    ProductProfile,
    ProductSize,
    ProductStatus,
    ProductTag,
)


class Command(BaseCommand):
    help = "Seed ProductCategory, ProductSize, ProductProfile, Product, and ProductTag rows."

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_or_create(self, model, label, **kwargs):
        obj, created = model.objects.get_or_create(**kwargs)
        status = "created" if created else "already exists"
        self.stdout.write(f"  [{label}] {obj} — {status}")
        return obj

    # ------------------------------------------------------------------
    # Main
    # ------------------------------------------------------------------

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Seeding ProductCategories ==="))
        cat_rte = self._get_or_create(ProductCategory, "Category", name="Ready to Eat",  defaults={"description": "Products that are ready to consume directly."})
        cat_rtc = self._get_or_create(ProductCategory, "Category", name="Ready to Cook", defaults={"description": "Products that require minimal cooking before consumption."})
        cat_rf  = self._get_or_create(ProductCategory, "Category", name="Raw Flour",     defaults={"description": "Raw flour blends and multigrain mixes for home cooking."})

        # ------------------------------------------------------------------
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Fetching ProductStatuses ==="))
        st_in_stock = ProductStatus.objects.get(status_name="IN_STOCK")
        st_low      = ProductStatus.objects.get(status_name="LOW")
        self.stdout.write(f"  IN_STOCK → pk={st_in_stock.pk}")
        self.stdout.write(f"  LOW      → pk={st_low.pk}")

        # ------------------------------------------------------------------
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Seeding ProductSizes ==="))
        sz_80g  = self._get_or_create(ProductSize, "Size", size_name="SMALL",  weight=80,   unit="g")
        sz_150g = self._get_or_create(ProductSize, "Size", size_name="SMALL",  weight=150,  unit="g")
        sz_200g = self._get_or_create(ProductSize, "Size", size_name="SMALL",  weight=200,  unit="g")
        sz_400g = self._get_or_create(ProductSize, "Size", size_name="MEDIUM", weight=400,  unit="g")
        sz_500g = self._get_or_create(ProductSize, "Size", size_name="MEDIUM", weight=500,  unit="g")
        sz_1kg  = self._get_or_create(ProductSize, "Size", size_name="LARGE",  weight=1000, unit="g")

        # ------------------------------------------------------------------
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Seeding Products ==="))

        PRODUCTS = [
            # ---------------------------------------------------------------
            # 1. Multi Millets Hakka Noodles
            # ---------------------------------------------------------------
            {
                "name": "Multi Millets Hakka Noodles",
                "description": "Power of 5 millets in every bite",
                "category": cat_rtc,
                "status": st_in_stock,
                "size": sz_200g,
                "fixed_price": "149.00",
                "discounted_price": "129.00",
                "quantity": 200,
                "is_trending": True,
                "profile": {
                    "calories": "388.20",
                    "protein": "4.79",
                    "carbohydrates": "92.26",
                    "fibre": "9.70",
                    "fats": "0.50",
                    "additional_info": {
                        "sodium": "2.1 g",
                        "ingredients": {
                            "main": "60% unpolished millet, cluster bean, whole wheat, salt.",
                            "tastemaker": "coriander powder, turmeric powder, onion powder, garlic powder, ginger powder, green chillies, cumin powder, garam masala",
                        },
                    },
                },
                "tags": ["#NoMaida", "#HighFiber", "#NutritiusChoice", "#Healthy&Tasty", "#100%Vegetarian"],
            },
            # ---------------------------------------------------------------
            # 2. Multi Millets Pasta
            # ---------------------------------------------------------------
            {
                "name": "Multi Millets Pasta",
                "description": "Made with multi millets",
                "category": cat_rtc,
                "status": st_in_stock,
                "size": sz_200g,
                "fixed_price": "149.00",
                "discounted_price": "129.00",
                "quantity": 180,
                "is_trending": True,
                "profile": {
                    "calories": "388.20",
                    "protein": "4.79",
                    "carbohydrates": "92.26",
                    "fibre": "9.76",
                    "fats": "0.50",
                    "additional_info": {
                        "sodium": "2.1 g",
                        "ingredients": {
                            "main": "60% unpolished millet, cluster bean, whole wheat, salt.",
                            "tastemaker": "coriander powder, turmeric powder, onion powder, garlic powder, green chillies, cumin powder, garam masala",
                        },
                    },
                },
                "tags": ["#NoMaida", "#HighFiber", "#RichInNutrients", "#EasyToCook", "#Healthy&Tasty", "#SmartPastaChoice", "#NutritionInEveryBite"],
            },
            # ---------------------------------------------------------------
            # 3. Multi Millets Soya Chips Chatpata Masala
            # ---------------------------------------------------------------
            {
                "name": "Multi Millets Soya Chips Chatpata Masala",
                "description": "High protein soya chips with chatpata masala flavor",
                "category": cat_rte,
                "status": st_in_stock,
                "size": sz_80g,
                "fixed_price": "60.00",
                "discounted_price": "50.00",
                "quantity": 350,
                "is_trending": True,
                "profile": {
                    "calories": "516.80",
                    "protein": "11.80",
                    "carbohydrates": "55.60",
                    "fibre": None,
                    "fats": "27.50",
                    "additional_info": {
                        "total_sugar": "1.9 g",
                        "trans_fat": "0.0 g",
                        "saturated_fat": "13.8 g",
                        "iron": "5.3 mg",
                        "potassium": "755.2 mg",
                        "ingredients": {
                            "main": "soya flour 48%, urad daal, rice flour, tapioca starch, himalayan pink salt, dry mango powder, sunflower oil, ajwain, spices and condiments",
                        },
                    },
                },
                "tags": ["#HighProtein", "#NoSugar", "#NoAdditives", "#NoPreservatives", "#ChatpataMasala", "#Crispy&Crunchy", "#LightSnack", "#NoMaida", "#AnytimeMunching"],
            },
            # ---------------------------------------------------------------
            # 4. Chocolate Almond Cookies
            # ---------------------------------------------------------------
            {
                "name": "Chocolate Almond Cookies",
                "description": "Rich chocolate almond cookies made with multi millets",
                "category": cat_rte,
                "status": st_low,
                "size": sz_150g,
                "fixed_price": "199.00",
                "discounted_price": "179.00",
                "quantity": 40,
                "is_trending": True,
                "profile": {
                    "calories": "496.00",
                    "protein": "8.90",
                    "carbohydrates": "56.30",
                    "fibre": "2.00",
                    "fats": "22.50",
                    "additional_info": {
                        "sugar": "26.8 g",
                        "sodium": "0.1 g",
                        "ingredients": {
                            "main": "70% multi millet flour and grain flour, unrefined sugar, ghee, chocolate & cocoa, almonds, baking soda, natural binding agent",
                        },
                    },
                },
                "tags": ["#RichChocolateFlavor", "#NoMaida", "#HighFiber", "#Crunchy&Delicious", "#HealthySnacking", "#MilletPowered", "#AnytimeMunching"],
            },
            # ---------------------------------------------------------------
            # 5. Millets Butter Kaju Cookies
            # ---------------------------------------------------------------
            {
                "name": "Millets Butter Kaju Cookies",
                "description": "Rich buttery cookies loaded with crunchy kaju goodness",
                "category": cat_rte,
                "status": st_in_stock,
                "size": sz_150g,
                "fixed_price": "219.00",
                "discounted_price": "199.00",
                "quantity": 120,
                "is_trending": True,
                "profile": {
                    "calories": "542.00",
                    "protein": "8.20",
                    "carbohydrates": "66.20",
                    "fibre": None,
                    "fats": "27.20",
                    "additional_info": {
                        "sugar": "8 g",
                        "sodium": "15 mg",
                        "ingredients": {
                            "main": "millet flour blend, wheat flour, butter, rice bran oil, milk powder, desi khand, elaichi powder, salt, baking soda, baking powder, custard powder, cashews",
                        },
                    },
                },
                "tags": ["#RichButtery", "#KajuLoaded", "#NoMaida", "#HighFiber", "#Wholesome", "#TeaTimeSnack", "#ClassicTaste"],
            },
            # ---------------------------------------------------------------
            # 6. Millet Energy Bar Chocolate Light
            # ---------------------------------------------------------------
            {
                "name": "Millet Energy Bar Chocolate Light",
                "description": "Healthy millet-based energy bars made with natural sugars and no added preservatives",
                "category": cat_rte,
                "status": st_in_stock,
                "size": sz_80g,
                "fixed_price": "120.00",
                "discounted_price": "99.00",
                "quantity": 250,
                "is_trending": True,
                "profile": {
                    "calories": "437.50",   # midpoint of 430–445
                    "protein": "10.50",     # midpoint of 10–11
                    "carbohydrates": "56.50",  # midpoint of 55–58
                    "fibre": "8.00",        # midpoint of 7–9
                    "fats": "18.00",        # midpoint of 17–19
                    "additional_info": {
                        "sugar": "28–32 g",
                        "note": "Nutritional values are approximate ranges.",
                        "ingredients": {
                            "main": "dates, oats, jowar flakes, oats, liquid glucose, honey, almonds, peanuts, psyllium husk, flaxseed powder, soy lecithin, cocoa, ghee/coconut oil, rosemary extract, salt",
                        },
                    },
                },
                "tags": ["#EnergyBars", "#NoAddedSugar", "#NaturalSugars", "#HealthyBites", "#NoPreservatives", "#NoFlavors", "#NoColors"],
            },
            # ---------------------------------------------------------------
            # 7. Millet Energy Bar Chocolate with Nuts
            # ---------------------------------------------------------------
            {
                "name": "Millet Energy Bar Chocolate with Nuts",
                "description": "Nut-rich millet energy bar with natural sugars and plant-based protein",
                "category": cat_rte,
                "status": st_low,
                "size": sz_80g,
                "fixed_price": "140.00",
                "discounted_price": "119.00",
                "quantity": 35,
                "is_trending": True,
                "profile": {
                    "calories": "460.00",   # midpoint of 450–470
                    "protein": "12.00",     # midpoint of 11–13
                    "carbohydrates": "52.00",  # midpoint of 50–54
                    "fibre": "9.00",        # midpoint of 8–10
                    "fats": "21.50",        # midpoint of 20–23
                    "additional_info": {
                        "sugar": "26–30 g",
                        "note": "Nutritional values are approximate ranges.",
                        "ingredients": {
                            "main": "dates, oats, jowar flakes, oats, liquid glucose, honey, almonds, soy lecithin, peanuts, psyllium husk, flaxseed, chia seed, pumpkin seed, cinnamon, coconut oil, cocoa, rosemary extract, sunflower seed",
                        },
                    },
                },
                "tags": ["#RichInFiber", "#PlantProtein", "#GlutenFree", "#WeightManagement", "#NoAddedSugar", "#NaturalSugars", "#HealthyBites", "#NoPreservatives", "#NoFlavors", "#NoColors"],
            },
            # ---------------------------------------------------------------
            # 8. Millet Granola Muesli Chocolate
            # ---------------------------------------------------------------
            {
                "name": "Millet Granola Muesli Chocolate",
                "description": "High fiber, high protein millet-based granola muesli for daily healthy nutrition",
                "category": cat_rte,
                "status": st_in_stock,
                "size": sz_400g,
                "fixed_price": "349.00",
                "discounted_price": "299.00",
                "quantity": 150,
                "is_trending": True,
                "profile": {
                    "calories": "317.51",
                    "protein": "7.68",
                    "carbohydrates": "44.813",
                    "fibre": "2.97",
                    "fats": "10.766",
                    "additional_info": {
                        "iron": "2.866 mg",
                        "calcium": "79.1 mg",
                        "ingredients": {
                            "main": "ragi flakes, jowar flakes, rolled oats, chipped almond, whole raisins, flaxseeds, vanilla powder, honey, berries, Himalayan pink salt, rosemary extract",
                        },
                    },
                },
                "tags": ["#HighFiber", "#HighProtein", "#HighNutrition", "#HighEnergy", "#RichInMinerals", "#PremiumIngredients", "#DailyWellness"],
            },
            # ---------------------------------------------------------------
            # 9. Multi Grain Flour Chocolate
            # ---------------------------------------------------------------
            {
                "name": "Multi Grain Flour Chocolate",
                "description": "High fiber, high protein multigrain flour for better nutrition and gut health",
                "category": cat_rf,
                "status": st_in_stock,
                "size": sz_500g,
                "fixed_price": "249.00",
                "discounted_price": "219.00",
                "quantity": 200,
                "is_trending": True,
                "profile": {
                    "calories": "360.00",
                    "protein": "14.00",
                    "carbohydrates": "70.00",
                    "fibre": "10.00",
                    "fats": "5.00",
                    "additional_info": {
                        "saturated_fat": "0.8 g",
                        "trans_fat": "0 g",
                        "cholesterol": "0 mg",
                        "total_sugar": "2.5 g",
                        "added_sugar": "0 g",
                        "calcium": "90 mg",
                        "iron": "4 mg",
                        "potassium": "340 mg",
                        "ingredients": {
                            "main": "wheat, ghat, chana roasted, moong daal roasted, soybean roasted, corn, jowar, bajra, ragi, flax seed roasted, methi roasted",
                        },
                    },
                },
                "tags": ["#HighFiber", "#HighProtein", "#GoodForGut", "#HighNutrition", "#HighEnergy", "#HighRorinace"],
            },
            # ---------------------------------------------------------------
            # 10. Multi Millets Namkeen Mixture
            # ---------------------------------------------------------------
            {
                "name": "Multi Millets Namkeen Mixture",
                "description": "Crunchy and tasty millet-based snack made with nutritious ingredients for healthy snacking",
                "category": cat_rte,
                "status": st_in_stock,
                "size": sz_150g,
                "fixed_price": "99.00",
                "discounted_price": "85.00",
                "quantity": 300,
                "is_trending": True,
                "profile": {
                    "calories": "480.50",
                    "protein": "10.80",
                    "carbohydrates": "60.00",
                    "fibre": "7.50",
                    "fats": "20.40",
                    "additional_info": {
                        "sugar": "0.6 g",
                        "sodium": "501 mg",
                        "ingredients": {
                            "main": "multi millet crispies, multi millet chips, aloo lachcha, chana jor garam, bhujia sev, popped bajra, moong jor garam, millet flakes",
                            "tastemaker": "chaat masala, turmeric powder, onion powder, garlic powder, kadi patta powder, salt, red chilli powder, hing powder, dry ginger powder, roasted cumin powder",
                        },
                    },
                },
                "tags": ["#NutritiousMillets", "#CrunchySnack", "#HighFiber", "#NoMaida", "#LightAndHealthy", "#AnytimeSnacking"],
            },
        ]

        # ------------------------------------------------------------------
        # Bulk create loop
        # ------------------------------------------------------------------
        for data in PRODUCTS:
            name = data["name"]
            self.stdout.write(f"\n  → {name}")

            # 1. ProductProfile
            profile_data = data.pop("profile")
            additional_info = profile_data.pop("additional_info", None)
            profile, p_created = ProductProfile.objects.get_or_create(
                additional_info=additional_info,
                defaults={**profile_data},
            )
            # If it already existed without the extras, just reuse it
            if p_created:
                # Re-save to make sure all fields are set (get_or_create only sets defaults on create)
                for field, val in profile_data.items():
                    setattr(profile, field, val)
                profile.additional_info = additional_info
                profile.save()
            self.stdout.write(f"    Profile pk={profile.pk} ({'created' if p_created else 'reused'})")

            # 2. Product
            tags_list = data.pop("tags")
            product, prod_created = Product.objects.get_or_create(
                name=name,
                defaults={
                    **data,
                    "profile": profile,
                },
            )
            if not prod_created:
                # Keep existing PID; just refresh mutable fields
                for field, val in data.items():
                    setattr(product, field, val)
                product.profile = profile
                product.save()
            self.stdout.write(f"    Product PID={product.pid} ({'created' if prod_created else 'updated'})")

            # 3. ProductTags
            for tag_name in tags_list:
                tag, t_created = ProductTag.objects.get_or_create(
                    product=product,
                    tag_name=tag_name,
                    defaults={"tag_description": ""},
                )
                if t_created:
                    self.stdout.write(f"    Tag: {tag_name}")

        self.stdout.write(self.style.SUCCESS("\n✅  Seeding complete!"))