import copy
import xml.etree.ElementTree as ET
import os
import re
import uuid
import subprocess
from wand.image import Image
from wand.drawing import Drawing

globalKeys = {
    "ModName": "PF2",
    "ModFolder": "Pathfinder2ndEdition_dda83752-5c01-30f9-6a09-824c7e182090",
    "AtlasUUID": "577ce84c-2418-5dfb-e911-eb56389c8543"
}

keys = [
    "Reference",
    "ObjectUUID",
    "RootTemplateUUID",
    "TranslationKeyDisplayName",
    "Traditions",
    "LearnReference",
    "UseCosts",
    "Categories",
    "RarityValue",
    "CharacterLevel",
    "ScrollIcon"
]

spellListClasses = {
    "Arcane": "Wizard",
    "Divine": "Cleric",
    "Occult": "Bard",
    "Primal": "Druid"
}

spellStatSources = [
    "../../Editor/Mods/Shared/Stats/SpellData/",
    "../../Editor/Mods/SharedDev/Stats/SpellData/",
    "../../Editor/Mods/Gustav/Stats/SpellData/",
    "../../Editor/Mods/GustavDev/Stats/SpellData/",
    "../../Editor/Mods/GustavX/Stats/SpellData/"
]

hasTraditionString = "HasPassive(&quot;Tradition_$$$&quot;, context.Source)"

outputSpells = []


def get_field(target, field, allSpells, fileType, handle=False):
    usingTarget = ""
    accessString = "value"
    if handle:
        accessString = "handle"
    localFields = target.find("fields").findall("field")
    # Check for a locally defined value
    for current in localFields:
        if current.attrib["name"] == field:
            try:
                return current.attrib[accessString]
            except:
                return ""
    # Find the UUID of the parent
    for current in localFields:
        if current.attrib["name"] == "Using":
            usingTarget = current.attrib["value"]
            break
    # Search for that UUID locally
    if usingTarget != "":
        for base in allSpells:
            baseFields = base.find("fields").findall("field")
            for baseField in baseFields:
                if baseField.attrib["name"] == "UUID":
                    if baseField.attrib["value"] == usingTarget:
                        # Recursive call to check further inheritance
                        return get_field(base, field, allSpells, fileType, handle=handle)
        # Search for that UUID in other stats files
        for directory in spellStatSources:
            try:
                spellsTree = ET.parse(directory + fileType).getroot()
                spellsData = spellsTree.find("stat_objects").findall("stat_object")
                for base in spellsData:
                    baseFields = base.find("fields").findall("field")
                    for baseField in baseFields:
                        if baseField.attrib["name"] == "UUID":
                            if baseField.attrib["value"] == usingTarget:
                                # Recursive call to check further inheritance
                                return get_field(base, field, allSpells, fileType, handle=handle)
            except:
                pass
    return ""


def generate_root_template(spell):
    templateFile = open("Templates/templateRootTemplate.lsx")
    newContent = templateFile.read()
    templateFile.close()
    for key in keys:
        newContent = newContent.replace("%" + key + "%", spell[key])
    for key, value in globalKeys.items():
        newContent = newContent.replace("%" + key + "%", value)
    with open("Output/RootTemplates/" + spell["RootTemplateUUID"] + ".lsx", "w") as output:
        output.write(newContent)


def convert_stats_template(spell, stats):
    for key in keys:
        stats = stats.replace("%" + key + "%", spell[key])
    for key, value in globalKeys.items():
        stats = stats.replace("%" + key + "%", value)
    return stats


def add_translation_to_file(newKey, newText):
    tree = ET.parse("../../Mods/" + globalKeys["ModFolder"] + "/Localization/English/english.xml")
    root = tree.getroot()
    newEntry = ET.SubElement(root, "content")
    newEntry.set("contentuid", newKey)
    newEntry.set("version", "1")
    newEntry.text = newText
    ET.indent(tree)
    with open("../../Mods/" + globalKeys["ModFolder"] + "/Localization/English/english.xml", "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True)


if __name__ == '__main__':
    # Delete all root templates in the output and temp folders
    for rootName in os.listdir("Output/RootTemplates"):
        if rootName != ".gitignore":
            os.remove("Output/RootTemplates/" + rootName)
    for rootName in os.listdir("Temp/RootTemplates"):
        if rootName != ".gitignore":
            os.remove("Temp/RootTemplates/" + rootName)
    # Generate a dict of all translated strings for our mod. As the TUID is the key, we don't need to do any horrible
    # searching each time we want to pull something out.
    translationDict = {}
    tree = ET.parse("../../Mods/" + globalKeys["ModFolder"] + "/Localization/English/english.xml")
    root = tree.getroot()
    translationContent = root.findall("content")
    for content in translationContent:
        translationDict[content.text] = content.attrib["contentuid"]

    # Generate a list of all the spell names we are looking for based on the tradition lists.
    listsTree = ET.parse("../../Editor/Mods/" + globalKeys["ModFolder"] + "/Lists/SpellLists.tbl")
    listsData = listsTree.find("stat_objects").findall("stat_object")
    fullTraditionStrings = {}
    fullTraditionLists = {}
    for tradition, traditionClass in spellListClasses.items():
        fullTraditionStrings[traditionClass] = ""
        fullTraditionLists[tradition] = set()
    for each in listsData:
        localFields = each.find("fields").findall("field")
        for tradition, traditionClass in spellListClasses.items():
            for field in localFields:
                if field.attrib["name"] == "Name":
                    if field.attrib["value"].startswith(traditionClass):
                        for field2 in localFields:
                            if field2.attrib["name"] == "Spells":
                                fullTraditionStrings[traditionClass] = fullTraditionStrings[traditionClass] + ";" + field2.attrib["value"]
    for tradition, traditionClass in spellListClasses.items():
        for each in fullTraditionStrings[traditionClass].split(";"):
            if each != "":
                fullTraditionLists[tradition].add(each)

    # Convert all of our mod's root templates to non-binary format for parsing using Divine and
    # look through the root templates to find scrolls that already exist, to avoid duplicates.
    relativePathInput = "../../Public/" + globalKeys["ModFolder"] + "/RootTemplates"
    absolutePathInput = os.path.abspath(relativePathInput)
    relativePathOutput = "Temp/RootTemplates"
    absolutePathOutput = os.path.abspath(relativePathOutput)
    subprocess.check_call("Divine.exe -a convert-resources -g bg3 -s \"" + absolutePathInput + "\" -d \"" + absolutePathOutput + "\" -i lsf -o lsx -l off")

    spells = []
    icons = set()
    icons.add("PF2_Item_LOOT_Scroll_Default.DDS")
    # Iterate over files in directory
    for fileName in os.listdir("../../Editor/Mods/" + globalKeys["ModFolder"] + "/Stats/SpellData"):
        # Skip SpellSet.stats
        if fileName == "SpellSet.stats":
            continue
        # Open spell stats file
        spellsTree = ET.parse("../../Editor/Mods/" + globalKeys["ModFolder"] + "/Stats/SpellData/" + fileName).getroot()
        spellsData = spellsTree.find("stat_objects").findall("stat_object")
        for each in spellsData:
            newSpellStats = {}
            useCost = get_field(each, "UseCosts", spellsData, fileName)
            if useCost.find("SpellSlotsGroup") != -1:
                newSpellStats["UseCosts"] = re.sub("SpellSlotsGroup:\d*:\d*:\d*", "", useCost)
            else:
                newSpellStats["UseCosts"] = useCost
            # Clear any trailing ;s in our useCost. Lazy but just running the test three time does the job
            if newSpellStats["UseCosts"][-1:] == ";":
                newSpellStats["UseCosts"] = newSpellStats["UseCosts"][:-1]
            if newSpellStats["UseCosts"][-1:] == ";":
                newSpellStats["UseCosts"] = newSpellStats["UseCosts"][:-1]
            if newSpellStats["UseCosts"][-1:] == ";":
                newSpellStats["UseCosts"] = newSpellStats["UseCosts"][:-1]

            # Skip AI variants of spells, if titled as such
            tempName = get_field(each, "Name", spellsData, fileName)
            if tempName.find("_AI") != -1:
                continue
            newSpellStats["Reference"] = fileName.replace(".stats", "") + "_" + tempName

            # If a spell is part of a container spell, skip it
            if get_field(each, "SpellContainerID", spellsData, fileName):
                continue

            # Learning a spell should grant its base version
            newSpellStats["LearnReference"] = get_field(each, "RootSpellID", spellsData, fileName)
            # Check the Owner field for manual learn reference overrides, used for ranked container spells
            newSpellStats["LearnReference"] = get_field(each, "Owner", spellsData, fileName) or newSpellStats["LearnReference"]
            # If not found the spell should grant itself when learnt
            newSpellStats["LearnReference"] = newSpellStats["LearnReference"] or newSpellStats["Reference"]

            # Check the spell lists calculated earlier to work out each spell's traditions
            newSpellStats["Traditions"] = ""
            for tradition in fullTraditionLists:
                for listSpell in fullTraditionLists[tradition]:
                    if newSpellStats["LearnReference"] == listSpell:
                        if newSpellStats["Traditions"] != "":
                            newSpellStats["Traditions"] = newSpellStats["Traditions"] + " or "
                        newSpellStats["Traditions"] = newSpellStats["Traditions"] + hasTraditionString.replace("$$$", tradition)
                        break
            if newSpellStats["Traditions"] == "":
                continue

            # Container spells should be skipped if their list ends in a semicolon.
            containerSpells = get_field(each, "ContainerSpells", spellsData, fileName)
            if containerSpells[-1:] == ";":
                print("Warning: Container spell skipped due to semicolon terminated container spell list - " + newSpellStats["Reference"])
                continue
            elif containerSpells != "":
                print("Info: Container spell found - " + newSpellStats["Reference"])

            spellIconSource = get_field(each, "Icon", spellsData, fileName)
            try:
                if not (os.path.isfile("../../Mods/" + globalKeys["ModFolder"] + "/GUI/Assets/ControllerUIIcons/items_png/" + globalKeys["ModName"] + "_Item_LOOT_Scroll_" + spellIconSource + ".DDS")
                        and os.path.isfile("../../Mods/" + globalKeys["ModFolder"] + "/GUI/AssetsLowRes/ControllerUIIcons/items_png/" + globalKeys["ModName"] + "_Item_LOOT_Scroll_" + spellIconSource + ".DDS")):
                    # Generate and save controller icons, which are also used as the basis for hotbar icons later
                    with Image(filename="Input/Icons/" + spellIconSource + ".DDS") as spellIcon:
                        spellIcon.resize(80, 83)
                        spellIcon.rotate(6)
                        # Make a blurry background copy of the spell icon for legibility
                        with Image(filename="Input/Icons/" + spellIconSource + ".DDS") as spellIcon2:
                            spellIcon2.resize(80, 83)
                            spellIcon2.rotate(6)
                            spellIcon2.blur(radius=5)
                            spellIcon2.modulate(brightness=70.0, saturation=130.0)
                            with Image(filename="Input/Icons/BlankScroll.png") as scrollImg:
                                drawing2 = Drawing()
                                drawing2.composite(operator='over', left=28, top=25, width=spellIcon2.width, height=spellIcon2.height, image=spellIcon2)
                                drawing2(scrollImg)
                                drawing = Drawing()
                                drawing.composite(operator='over', left=28, top=25, width=spellIcon.width, height=spellIcon.height, image=spellIcon)
                                drawing(scrollImg)
                                scrollImg.compression = "dxt5"
                                scrollImg.save(filename="../../Mods/" + globalKeys["ModFolder"] + "/GUI/Assets/ControllerUIIcons/items_png/" + globalKeys["ModName"] + "_Item_LOOT_Scroll_" + spellIconSource + ".DDS")
                                scrollImg.resize(72, 72)
                                scrollImg.save(filename="../../Mods/" + globalKeys["ModFolder"] + "/GUI/AssetsLowRes/ControllerUIIcons/items_png/" + globalKeys["ModName"] + "_Item_LOOT_Scroll_" + spellIconSource + ".DDS")
                newSpellStats["ScrollIcon"] = globalKeys["ModName"] + "_Item_LOOT_Scroll_" + spellIconSource
                if not (os.path.isfile("../../Mods/" + globalKeys["ModFolder"] + "/GUI/Assets/Tooltips/ItemIcons/" + globalKeys["ModName"] + "_Item_LOOT_Scroll_" + spellIconSource + ".DDS")
                        and os.path.isfile("../../Mods/" + globalKeys["ModFolder"] + "/GUI/AssetsLowRes/Tooltips/ItemIcons/" + globalKeys["ModName"] + "_Item_LOOT_Scroll_" + spellIconSource + ".DDS")):
                    with Image(filename="Input/Icons/" + spellIconSource + ".DDS") as spellIcon:
                        spellIcon.resize(200, 220)
                        spellIcon.rotate(8)
                        with Image(filename="Input/Icons/" + spellIconSource + ".DDS") as spellIcon2:
                            spellIcon2.resize(200, 220)
                            spellIcon2.rotate(8)
                            spellIcon2.blur(radius=12)
                            spellIcon2.modulate(brightness=70.0, saturation=130.0)
                            with Image(filename="Input/Icons/Large/BlankScroll.png") as scrollImg:
                                drawing2 = Drawing()
                                drawing2.composite(operator='over', left=73, top=53, width=spellIcon2.width, height=spellIcon2.height, image=spellIcon2)
                                drawing2(scrollImg)
                                drawing = Drawing()
                                drawing.composite(operator='over', left=73, top=53, width=spellIcon.width, height=spellIcon.height, image=spellIcon)
                                drawing(scrollImg)
                                scrollImg.compression = "dxt5"
                                scrollImg.save(filename="../../Mods/" + globalKeys["ModFolder"] + "/GUI/Assets/Tooltips/ItemIcons/" + globalKeys["ModName"] + "_Item_LOOT_Scroll_" + spellIconSource + ".DDS")
                                scrollImg.resize(192, 192)
                                scrollImg.save(filename="../../Mods/" + globalKeys["ModFolder"] + "/GUI/AssetsLowRes/Tooltips/ItemIcons/" + globalKeys["ModName"] + "_Item_LOOT_Scroll_" + spellIconSource + ".DDS")
                icons.add(globalKeys["ModName"] + "_Item_LOOT_Scroll_" + spellIconSource + ".DDS")
            except:
                print("Warning: Spell icon not present in provided icons - " + newSpellStats["Reference"])
                newSpellStats["ScrollIcon"] = globalKeys["ModName"] + "_Item_LOOT_Scroll_Default"

            newSpellStats["RootTemplateUUID"] = ""
            for rootName in os.listdir("Temp/RootTemplates"):
                rootTree = ET.parse("Temp/RootTemplates/" + rootName).getroot()
                rootData = rootTree.find("region").find("node").find("children").find("node").findall("attribute")
                match = ""
                for attribute in rootData:
                    if attribute.attrib["id"] == "Name":
                        if attribute.attrib["value"] == globalKeys["ModName"] + "_LOOT_SCROLL_" + newSpellStats["Reference"]:
                            match = rootName.replace(".lsx", "")
                        break
                if match:
                    newSpellStats["RootTemplateUUID"] = match
                    break

            # Generate UUIDs if the searches failed
            newSpellStats["RootTemplateUUID"] = newSpellStats["RootTemplateUUID"] or str(uuid.uuid4())

            # Dummy value for now, will be generated at write time
            newSpellStats["ObjectUUID"] = ""

            # Find the spell's display name
            displayName = ""
            displayNameKey = get_field(each, "DisplayName", spellsData, fileName, handle=True)
            for entry in translationDict:
                if translationDict[entry] == displayNameKey:
                    displayName = entry
            if displayName == "":
                continue

            # Check for existing translation string key
            newSpellStats["TranslationKeyDisplayName"] = ""
            for text, key in translationDict.items():
                if text == "Scroll of " + displayName:
                    newSpellStats["TranslationKeyDisplayName"] = key
            if newSpellStats["TranslationKeyDisplayName"] == "":
                newSpellStats["TranslationKeyDisplayName"] = "h" + str(uuid.uuid4()).replace("-", "g")
                translationDict["Scroll of " + displayName] = newSpellStats["TranslationKeyDisplayName"]
                add_translation_to_file(newSpellStats["TranslationKeyDisplayName"], "Scroll of " + displayName)

            # Some data requires us know the spell's level
            tempRank = get_field(each, "Level", spellsData, fileName)
            try:
                tempRankInt = int(tempRank)
            except:
                tempRankInt = 0
            if tempRankInt > 1:
                newSpellStats["Categories"] = "MagicScroll_" + tempRank
            else:
                newSpellStats["Categories"] = "MagicScroll"
            # Sets the shop value, not that values over 12 seem to break the stats file, so we cap it.
            newSpellStats["CharacterLevel"] = str(min(max((tempRankInt * 2) - 1, 1), 12))
            # Rarity is just about spell rank
            if 1 < tempRankInt < 4:
                newSpellStats["RarityValue"] = "Uncommon"
            elif 3 < tempRankInt < 6:
                newSpellStats["RarityValue"] = "Rare"
            elif 5 < tempRankInt:
                newSpellStats["RarityValue"] = "VeryRare"
            else:
                newSpellStats["RarityValue"] = ""

            # Some spell schools have specialised additional loot lists
            tempSpellSchool = get_field(each, "SpellSchool", spellsData, fileName)
            if tempSpellSchool == "Necromancy":
                extraString = newSpellStats["Categories"].replace("MagicScroll", "MagicScroll_Necro")
                newSpellStats["Categories"] = newSpellStats["Categories"] + ";" + extraString
            elif tempSpellSchool == "Illusion":
                extraString = newSpellStats["Categories"].replace("MagicScroll", "MagicScroll_Illusion")
                newSpellStats["Categories"] = newSpellStats["Categories"] + ";" + extraString
            elif tempSpellSchool == "Abjuration":
                extraString = newSpellStats["Categories"].replace("MagicScroll", "MagicScroll_Protection")
                newSpellStats["Categories"] = newSpellStats["Categories"] + ";" + extraString

            # Utility spells also have an additional loot table, so we check the cast intent, but only if
            # the spell is not already in another list
            if get_field(each, "VerbalIntent", spellsData, fileName) == "Utility":
                if newSpellStats["Categories"].find(";") == -1:
                    newSpellStats["Categories"] = newSpellStats["Categories"] + ";" + "MagicScroll_Utility"
                    # There is also a loot table for rare utility scrolls
                    try:
                        if newSpellStats["RarityValue"] == "Rare":
                            newSpellStats["Categories"] = newSpellStats["Categories"] + "_Rare"
                        if newSpellStats["RarityValue"] == "VeryRare":
                            newSpellStats["Categories"] = newSpellStats["Categories"] + "_Rare"
                    # If the scroll is common it won't have a rarity value
                    except:
                        pass
            outputSpells.append(newSpellStats)

    for spell in outputSpells:
        generate_root_template(spell)

    # Open original XML stats file to append to
    objectBase = ET.parse("../../Editor/Mods/" + globalKeys["ModFolder"] + "/Stats/Stats/Object.stats")
    objectTree = objectBase.getroot()
    objectStats = objectTree.find("stat_objects")
    for spell in outputSpells:
        for existing in objectStats.findall("stat_object"):
            localFields = existing.find("fields").findall("field")
            for field in localFields:
                if field.attrib["name"] == "Name":
                    if field.attrib["value"] == globalKeys["ModName"] + "_OBJ_Scroll_" + spell["Reference"]:
                        for field2 in localFields:
                            if field2.attrib["name"] == "UUID":
                                spell["ObjectUUID"] = field2.attrib["value"]
                                objectStats.remove(existing)
                                break
                        break
            if spell["ObjectUUID"] != "":
                break
        spell["ObjectUUID"] = spell["ObjectUUID"] or str(uuid.uuid4())
        with open("Templates/templateObjectStat.stats") as templateFile:
            stats = convert_stats_template(spell, templateFile.read())
        templateRoot = ET.ElementTree(ET.fromstring(stats)).getroot()
        template = templateRoot.find("stat_objects").find("stat_object")
        newStat = copy.deepcopy(template)
        if spell["RarityValue"] != "":
            rarity = ET.SubElement(newStat.find("fields"), "field")
            rarity.set("name", "Rarity")
            rarity.set("type", "EnumerationTableFieldDefinition")
            rarity.set("value", spell["RarityValue"])
            rarity.set("enumeration_type_name", "Rarity")
            rarity.set("version", "1")
        if spell["UseCosts"] != "ActionPoint:2":
            useCosts = ET.SubElement(newStat.find("fields"), "field")
            useCosts.set("name", "UseCosts")
            useCosts.set("type", "StringTableFieldDefinition")
            if spell["UseCosts"] == "":
                useCosts.set("clear_inherited_value", "true")
            useCosts.set("value", spell["UseCosts"])
        objectStats.append(newStat)
        ET.indent(objectTree)
    with open("../../Editor/Mods/" + globalKeys["ModFolder"] + "/Stats/Stats/Object.stats", "wb") as f:
        objectBase.write(f, encoding="utf-8", xml_declaration=True)

    with Image(filename="Input/Icons/" + globalKeys["ModName"] + "_Item_LOOT_Scroll_Default.DDS") as source:
        source.save(filename="../../Mods/" + globalKeys["ModFolder"] + "/GUI/Assets/ControllerUIIcons/items_png/" + globalKeys["ModName"] + "_Item_LOOT_Scroll_Default.DDS")
        source.resize(72, 72)
        source.save(filename="../../Mods/" + globalKeys["ModFolder"] + "/GUI/AssetsLowRes/ControllerUIIcons/items_png/" + globalKeys["ModName"] + "_Item_LOOT_Scroll_Default.DDS")
    with Image(filename="Input/Icons/Large/" + globalKeys["ModName"] + "_Item_LOOT_Scroll_Default.DDS") as source:
        source.save(filename="../../Mods/" + globalKeys["ModFolder"] + "/GUI/Assets/Tooltips/ItemIcons/" + globalKeys["ModName"] + "_Item_LOOT_Scroll_Default.DDS")
        source.resize(192, 192)
        source.save(filename="../../Mods/" + globalKeys["ModFolder"] + "/GUI/AssetsLowRes/Tooltips/ItemIcons/" + globalKeys["ModName"] + "_Item_LOOT_Scroll_Default.DDS")

    with Image(filename="Input/Icons/BlankAtlas.png") as blank:
        x = 0
        y = 0
        atlasBase = ET.parse("Templates/Icons_Items_Scrolls_Template.lsx")
        atlasTree = atlasBase.getroot()
        atlasRegions = atlasTree.findall("region")
        for each in atlasRegions:
            if each.attrib["id"] == "TextureAtlasInfo":
                node = ET.SubElement(each.find("node").find("children"), "node")
                node.set("id", "TextureAtlasPath")
                attribute = ET.SubElement(node, "attribute")
                attribute.set("id", "Path")
                attribute.set("type", "string")
                attribute.set("value", "Assets/Textures/Icons/Icons_Items_Scrolls_" + globalKeys["ModName"] + ".dds")
                attribute = ET.SubElement(node, "attribute")
                attribute.set("id", "UUID")
                attribute.set("type", "FixedString")
                attribute.set("value", globalKeys["AtlasUUID"])
            if each.attrib["id"] == "IconUVList":
                atlasUVList = each
        for each in icons:
            with Image(filename="../../Mods/" + globalKeys["ModFolder"] + "/GUI/Assets/ControllerUIIcons/items_png/" + each) as scrollImg:
                scrollImg.resize(64, 64)
                drawing = Drawing()
                drawing.composite(operator='over', left=x, top=y, width=scrollImg.width, height=scrollImg.height, image=scrollImg)
                drawing(blank)
                # Add details of the icon to the atlas UV list
                node = ET.SubElement(atlasUVList.find("node").find("children"), "node")
                node.set("id", "IconUV")
                attribute = ET.SubElement(node, "attribute")
                attribute.set("id", "MapKey")
                attribute.set("type", "FixedString")
                attribute.set("value", each.replace(".DDS", ""))
                attribute = ET.SubElement(node, "attribute")
                attribute.set("id", "U1")
                attribute.set("type", "float")
                attribute.set("value", "{:.5f}".format(x / blank.width))
                attribute = ET.SubElement(node, "attribute")
                attribute.set("id", "U2")
                attribute.set("type", "float")
                attribute.set("value", "{:.5f}".format((x + 64) / blank.width))
                attribute = ET.SubElement(node, "attribute")
                attribute.set("id", "V1")
                attribute.set("type", "float")
                attribute.set("value", "{:.5f}".format(y / blank.height))
                attribute = ET.SubElement(node, "attribute")
                attribute.set("id", "V2")
                attribute.set("type", "float")
                attribute.set("value", "{:.5f}".format((y + 64) / blank.height))
                # Increment the x and y co-ordinates
                x = x + 64
                if x >= blank.width:
                    y = y + 64
                    x = 0
        mergedBase = ET.parse("Templates/template_merged.lsx")
        mergedTree = mergedBase.getroot()
        mergedNode = mergedTree.find("region").find("node").find("children").find("node")
        for each in mergedNode.findall("attribute"):
            if each.attrib["id"] == "ID":
                each.attrib["value"] = globalKeys["AtlasUUID"]
            if each.attrib["id"] == "Name":
                each.attrib["value"] = "Icons_Items_Scrolls_" + globalKeys["ModName"]
            if each.attrib["id"] == "SourceFile":
                each.attrib["value"] = "Public/" + globalKeys["ModFolder"] + "/Assets/Textures/Icons/Icons_Items_Scrolls_" + globalKeys["ModName"] + ".dds"
            if each.attrib["id"] == "Template":
                each.attrib["value"] = "Icons_Items_Scrolls_" + globalKeys["ModName"]
        blank.compression = "dxt5"
        blank.save(filename="../../Public/" + globalKeys["ModFolder"] + "/Assets/Textures/Icons/Icons_Items_Scrolls_" + globalKeys["ModName"] + ".dds")
        ET.indent(atlasTree)
        with open("../../Public/" + globalKeys["ModFolder"] + "/GUI/Icons_Items_Scrolls_" + globalKeys["ModName"] + ".lsx", "wb") as f:
            atlasBase.write(f, encoding="utf-8", xml_declaration=True)
        with open("Output/AssetData/" + globalKeys["AtlasUUID"] + ".lsx", "wb") as f:
            mergedBase.write(f, encoding="utf-8", xml_declaration=True)

    # Delete any files that we intend to replace in RootTemplates
    for rootName in os.listdir("Output/RootTemplates"):
        try:
            os.remove("../../Public/" + globalKeys["ModFolder"] + "/RootTemplates/" + rootName.replace(".lsx", ".lsf"))
        except:
            pass
    try:
        os.remove("../../Public/" + globalKeys["ModFolder"] + "/Content/[PAK]_" + globalKeys["ModFolder"] + "/" + globalKeys["AtlasUUID"] + ".lsf")
    except:
        pass
    # Call divine to convert Output/RootTemplates to .lsf files
    relativePathOutput = "../../Public/" + globalKeys["ModFolder"] + "/RootTemplates"
    absolutePathOutput = os.path.abspath(relativePathOutput)
    relativePathInput = "Output/RootTemplates"
    absolutePathInput = os.path.abspath(relativePathInput)
    subprocess.check_call("Divine.exe -a convert-resources -g bg3 -s \"" + absolutePathInput + "\" -d \"" + absolutePathOutput + "\" -i lsx -o lsf -l off")
    #  Convert asset data output to .lsf
    relativePathOutput = "../../Public/" + globalKeys["ModFolder"] + "/Content/[PAK]_" + globalKeys["ModFolder"]
    absolutePathOutput = os.path.abspath(relativePathOutput)
    relativePathInput = "Output/AssetData"
    absolutePathInput = os.path.abspath(relativePathInput)
    subprocess.check_call("Divine.exe -a convert-resources -g bg3 -s \"" + absolutePathInput + "\" -d \"" + absolutePathOutput + "\" -i lsx -o lsf -l off")

    print("Complete")
