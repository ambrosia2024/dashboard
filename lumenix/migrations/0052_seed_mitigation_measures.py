from django.db import migrations

# First FAO/Codex mitigation corpus for Ambra (issue #112).
#
# Each row is a PARAPHRASE of one clause, not the clause's own wording: the
# authoritative text stays with Codex and every row links back to it. That keeps
# us clear of reproducing a published standard wholesale, and a clause-level
# control measure is a better retrieval unit than a page of PDF.
#
# Sources, read 24 November 2026 from codex.fao.org:
#   CXC 53-2003  Code of Hygienic Practice for Fresh Fruits and Vegetables
#                (adopted 2003; Annex III on fresh leafy vegetables added 2010;
#                latest revision 2017). No licence statement printed in the PDF.
#   CXG 61-2007  Guidelines on the Application of General Principles of Food
#                Hygiene to the Control of Listeria monocytogenes in Foods
#                (adopted 2007, revised 2026). CC BY-NC 4.0.
#   CXC 1-1969   General Principles of Food Hygiene (revised 2023).
#                CC BY-NC-SA 3.0 IGO - note the ShareAlike term.

CXC53 = {
    "source_code": "CXC 53-2003",
    "source_title": "Code of Hygienic Practice for Fresh Fruits and Vegetables",
    "source_url": "https://codex.fao.org/restapi/searchstandard/CXC_053e.pdf?lang=en&id=300",
    "source_licence": "",
    "revision_year": 2017,
}
CXG61 = {
    "source_code": "CXG 61-2007",
    "source_title": ("Guidelines on the Application of General Principles of Food Hygiene "
                     "to the Control of Listeria monocytogenes in Foods"),
    "source_url": "https://codex.fao.org/restapi/searchstandard/CXG_061e.pdf?lang=en&id=356",
    "source_licence": "CC BY-NC 4.0",
    "revision_year": 2026,
}
CXC1 = {
    "source_code": "CXC 1-1969",
    "source_title": "General Principles of Food Hygiene",
    "source_url": "https://codex.fao.org/restapi/searchstandard/CXC_001e.pdf?lang=en&id=23",
    "source_licence": "CC BY-NC-SA 3.0 IGO",
    "revision_year": 2023,
}

LEAFY = ["lettuce", "leafy vegetables", "fresh produce"]
PRODUCE = ["fresh produce", "fruits", "vegetables"]
LISTERIA = ["listeria monocytogenes"]

MEASURES = [
    # --- CXC 53-2003, main code ---
    (CXC53, "3.1.2", "Animals and human activity", "primary", PRODUCE, [], False,
     "Keep domestic and wild animals, and uncontrolled human traffic, out of growing areas where "
     "they could contaminate the crop, and assess neighbouring land use for the same risk."),
    (CXC53, "3.2.1.1.1", "Water for irrigation and harvesting", "primary", PRODUCE, [], False,
     "Choose an irrigation method by whether it wets the edible part of the crop. Overhead irrigation "
     "carries the highest risk because droplets wet the produce for hours and their impact can drive "
     "contamination into protected sites; subsurface or drip irrigation carries the least. Pay particular "
     "attention to water quality close to harvest, on crops whose leaves trap water, and on produce that "
     "will get little or no post-harvest washing."),
    (CXC53, "3.2.1.2", "Manure, biosolids and other natural fertilizers", "primary", PRODUCE, [], False,
     "Treat manure and other natural fertilizers before use, by composting or an equivalent method, because "
     "pathogens can persist in them for weeks or months. In general apply only fully composted material, and "
     "do not apply untreated or part-treated material after plant emergence or transplanting unless enough "
     "time is left before harvest for pathogen levels to fall."),
    (CXC53, "5.2.2.1", "Post-harvest water use", "processing", PRODUCE, [], False,
     "Match water quality to the stage: clean water may serve for initial washing, but final rinses should be "
     "of potable quality, and clean or preferably potable water should be used wherever water is applied under "
     "pressure or vacuum, since that can force pathogens into plant cells. Monitor and record biocide levels, "
     "and make ice from potable water."),
    (CXC53, "5.2.2.3", "Cooling of fresh fruits and vegetables", "harvest", PRODUCE, [], True,
     "Keep the cooling step from becoming the contamination step: condensate and defrost water must not drip "
     "onto produce, water or ice in direct contact must be potable and controlled, and cooling equipment must "
     "be cleaned and disinfected to a written procedure."),
    (CXC53, "5.2.2.4", "Cold storage", "storage", PRODUCE, [], True,
     "After cooling, hold produce at a temperature that minimises microbial growth, and control, monitor and "
     "record the cold-store temperature."),
    (CXC53, "5.8", "Recall procedures", "processing", PRODUCE, [], False,
     "Keep procedures that allow an unsafe lot to be identified and withdrawn from the market completely and "
     "quickly, with records that make the product traceable."),
    (CXC53, "6.3", "Pest-control systems", "processing", PRODUCE, [], False,
     "Run a pest-control programme for packing and processing premises, since pests are a vehicle for "
     "pathogens onto produce and onto contact surfaces."),

    # --- CXC 53-2003, Annex III: fresh leafy vegetables (this is the lettuce material) ---
    (CXC53, "Annex III 3.2.1.1.1", "Water for irrigation and harvesting (leafy vegetables)",
     "primary", LEAFY, [], False,
     "Leafy vegetables need particular care because rough surfaces, vase-like growth and dense planting let "
     "water collect on the leaf and give microbes somewhere to attach and survive. Irrigate so as to minimise "
     "wetting the edible portion, and use clean and preferably potable water wherever water touches the leaf, "
     "including the light sprays used to hydrate the crop during or just after machine harvest."),
    (CXC53, "Annex III 3.3.2", "Storage and transport from the field to the packing facility",
     "storage", LEAFY, [], True,
     "Hold leafy vegetables between 1 and 5 degrees Celsius throughout the supply chain, or otherwise keep the "
     "time they spend warmer than that as short as possible, to limit microbial proliferation. Some chill-sensitive "
     "herbs such as basil are an exception and may need a higher storage temperature, where shortening the warm "
     "period is the better control."),
    (CXC53, "Annex III 5.2.2.3", "Cooling of fresh leafy vegetables", "harvest", LEAFY, [], True,
     "Cool leafy vegetables as rapidly as possible after harvest, by a method that does not itself contaminate "
     "them - for example vacuum cooling for iceberg lettuce, forced-air cooling, hydrocooling, spray-vacuum "
     "cooling, or ice for parsley."),
    (CXC53, "Annex III 5.8", "Traceability and product tracing (leafy vegetables)", "processing", LEAFY, [], False,
     "Where a single salad pack combines ingredients from several sources, tracing a problem back becomes much "
     "harder, so keep records that identify the source of each ingredient in the product."),
    (CXC53, "Annex III 9.4", "Consumer education (leafy vegetables)", "consumer", LEAFY, [], False,
     "Tell consumers how to handle leafy vegetables safely: lettuce and similar leaves are fragile and bruising "
     "them invites contamination, and bagged produce must be labelled clearly enough that someone can tell "
     "whether it still needs washing. Anything not marked as washed and ready to eat should be washed."),

    # --- CXG 61-2007: Listeria monocytogenes ---
    (CXG61, "8", "Primary production", "primary", PRODUCE, LISTERIA, False,
     "Control on-farm operations to reduce the chance of Listeria monocytogenes entering the food chain and to "
     "prevent growth during storage and transport. Ready-to-eat foods that never receive a listericidal treatment, "
     "such as fresh produce, need more attention than those that do. Factors worth weighing include seasonality, "
     "the production method, and the effects of climate change - heavy rainfall and flooding can raise the amount "
     "of Listeria in soil, move more soil onto the crop, and degrade agricultural water quality."),
    (CXG61, "8.2", "Hygienic production", "primary", LEAFY, LISTERIA, False,
     "Design and maintain growing and harvesting equipment so that Listeria monocytogenes cannot find harbourage "
     "in it, which matters most for foods eaten without a listericidal step such as fresh leafy greens."),
    (CXG61, "8.3", "Handling, storage and transport", "harvest", PRODUCE, LISTERIA, True,
     "After harvest, hold ready-to-eat foods that get no listericidal treatment at temperatures that minimise "
     "Listeria growth, and keep the interval between harvest and storage as short as possible."),
    (CXG61, "8.4", "Cleaning, maintenance and personnel hygiene", "primary", PRODUCE, LISTERIA, False,
     "Clean and disinfect equipment used to grow, harvest and transport the crop often enough to keep Listeria "
     "monocytogenes off the food and out of the processing areas downstream, and verify periodically that the "
     "programme is working."),
    (CXG61, "13.2.1", "Time and temperature control", "storage", PRODUCE, LISTERIA, True,
     "Storage temperature is the single largest influence on listeriosis risk for foods that support growth. Where "
     "feasible the product should never exceed 5 degrees Celsius, and preferably sit between 2 and 4 degrees, "
     "where growth is markedly slower. Any loss of temperature control needs evaluating against the remaining "
     "shelf life, and the shelf life itself should be set so that growth stays controlled, allowing for the "
     "temperature abuse that realistically happens in distribution and in the home."),
    (CXG61, "13.2.2", "Specific process steps", "processing", PRODUCE, LISTERIA, False,
     "Validate any listericidal treatment and monitor the equipment parameters that make it work. For foods that "
     "receive no such treatment, apply specific measures to limit or prevent growth instead - shortening shelf "
     "life, reformulating, freezing, or a post-packaging treatment where accepted."),
    (CXG61, "13.2.4", "Microbiological contamination", "processing", PRODUCE, LISTERIA, False,
     "Listeria can reach ready-to-eat food at any step where it is exposed - from raw materials, people, aerosols, "
     "utensils, equipment or unclean surfaces, in primary production, processing, storage, transport, retail, "
     "catering and the home - so control traffic flow of people, product and equipment as well as the surfaces."),
    (CXG61, "Annex I", "Environmental monitoring programme for Listeria monocytogenes",
     "processing", PRODUCE, LISTERIA, False,
     "Run an environmental monitoring programme that samples and tests both food-contact and non-contact surfaces "
     "in primary production and processing areas, to verify that the hygiene controls are actually keeping Listeria "
     "out of exposed ready-to-eat food."),

    # --- CXC 1-1969: the general backstop ---
    (CXC1, "8.2", "Hygienic production (primary production)", "primary", [], [], False,
     "Consider at every primary production step whether the activity could make the food unsafe, and control the "
     "known routes in - the growing environment, agricultural inputs, water, and the people and equipment handling "
     "the crop."),
    (CXC1, "13.2.1", "Time and temperature control", "storage", [], [], True,
     "Put systems in place to control time and temperature wherever they bear on food safety, and make sure those "
     "systems account for the nature of the food, its intended shelf life, and how it will be stored and handled."),
    (CXC1, "13.3", "Water", "processing", [], [], False,
     "Water, and the ice and steam made from it, should be fit for the use it is put to, so that it does not itself "
     "become the route by which the food is contaminated."),
]

FIELDS = ("clause", "heading", "stage", "commodities", "hazards", "temperature_related", "measure")


def seed(apps, schema_editor):
    Measure = apps.get_model("lumenix", "MitigationMeasure")
    for source, clause, heading, stage, commodities, hazards, temp, measure in MEASURES:
        Measure.objects.update_or_create(
            source_code=source["source_code"],
            clause=clause,
            defaults={
                **source,
                "heading": heading,
                "stage": stage,
                "commodities": list(commodities),
                "hazards": list(hazards),
                "temperature_related": temp,
                "measure": " ".join(measure.split()),
                "status": 1,
            },
        )


def unseed(apps, schema_editor):
    Measure = apps.get_model("lumenix", "MitigationMeasure")
    for source, clause, *_ in MEASURES:
        Measure.objects.filter(source_code=source["source_code"], clause=clause).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("lumenix", "0051_mitigationmeasure"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
