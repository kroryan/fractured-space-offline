using UAssetAPI;
using UAssetAPI.UnrealTypes;
using Newtonsoft.Json.Linq;
using UAssetAPI.ExportTypes;

static UAsset Load(string path) => new(Path.GetFullPath(path), EngineVersion.VER_UE4_19);

if (args.Length == 2 && args[0] == "mesh-info")
{
    var asset = Load(args[1]);
    var exports = asset.Exports.OfType<NormalExport>().ToArray();
    var bound = exports.SelectMany(export => export.Data).Single(property => property.Name.ToString() == "ExtendedBounds");
    var fields = (JArray)JObject.Parse(asset.SerializeJsonObject(bound, false))["Value"]!;
    JToken Coordinates(JToken field) => field["Value"]![0]!["Value"]!.DeepClone();
    var bounds = new JObject();
    foreach (var name in new[] { "Origin", "BoxExtent" })
    {
        var vector = Coordinates(fields.Single(field => (string?)field["Name"] == name));
        bounds[name] = new JArray(new[] { "X", "Y", "Z" }.Select(axis => vector[axis]!.Value<double>()));
    }
    var sockets = new JArray();
    foreach (var export in exports)
    {
        var name = export.Data.FirstOrDefault(property => property.Name.ToString() == "SocketName");
        if (name is null) continue;
        var location = export.Data.Single(property => property.Name.ToString() == "RelativeLocation");
        var vector = Coordinates(JObject.Parse(asset.SerializeJsonObject(location, false)));
        var rotation = export.Data.FirstOrDefault(property => property.Name.ToString() == "RelativeRotation");
        var angles = rotation is null ? null : Coordinates(JObject.Parse(asset.SerializeJsonObject(rotation, false)));
        sockets.Add(new JObject {
            ["name"] = JObject.Parse(asset.SerializeJsonObject(name, false))["Value"]!.DeepClone(),
            ["rotation"] = new JArray(new[] { "Pitch", "Yaw", "Roll" }.Select(axis => angles?[axis]?.Value<double>() ?? 0)),
            ["location"] = new JArray(new[] { "X", "Y", "Z" }.Select(axis => vector[axis]!.Value<double>())) });
    }
    var materials = exports.SelectMany(export => export.Data).Single(property => property.Name.ToString() == "StaticMaterials");
    var materialCount = ((JArray)JObject.Parse(asset.SerializeJsonObject(materials, false))["Value"]!).Count;
    Console.WriteLine(new JObject { ["bounds"] = bounds, ["sockets"] = sockets, ["material_count"] = materialCount }.ToString());
    return;
}

if (args.Length == 3 && args[0] == "write")
{
    var destination = Path.GetFullPath(args[2]);
    Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
    UAsset.DeserializeJson(File.ReadAllText(args[1])).Write(destination);
    if (!Load(destination).VerifyBinaryEquality()) throw new InvalidDataException("Written asset failed binary round-trip verification.");
    Console.WriteLine("Wrote and verified " + Path.GetFileName(destination));
    return;
}

if (args.Length == 2 && args[0] == "check-lighting")
{
    const string required = "TBasePassVSFPrecomputedVolumetricLightmapLightingPolicy";
    var checkedMaterials = 0;
    foreach (var path in Directory.EnumerateFiles(Path.GetFullPath(args[1]), "*.uasset", SearchOption.AllDirectories))
    {
        var asset = Load(path);
        var material = asset.Exports.Any(export => export.ClassIndex.Index < 0 &&
            asset.Imports[-export.ClassIndex.Index - 1].ObjectName.ToString() == "Material");
        if (!material) continue;
        if (!asset.ContainsNameReference(new FString(required)))
            throw new InvalidDataException("Missing hangar volumetric-lightmap shader permutation: " + path);
        checkedMaterials++;
    }
    if (checkedMaterials == 0) throw new InvalidDataException("No cooked fleet materials found.");
    Console.WriteLine("Verified hangar volumetric-lightmap shader references in " + checkedMaterials + " cooked materials.");
    return;
}

if (args.Length == 2 && args[0] == "bounds")
{
    var asset = Load(args[1]);
    var bounds = asset.Exports.OfType<NormalExport>().SelectMany(export => export.Data)
        .Single(property => property.Name.ToString() == "ExtendedBounds");
    Console.WriteLine(asset.SerializeJsonObject(bounds, true));
    return;
}

if (args.Length == 3 && args[0] == "dump")
{
    var asset = Load(args[1]);
    Console.WriteLine("Binary round-trip equality: " + asset.VerifyBinaryEquality());
    File.WriteAllText(Path.GetFullPath(args[2]), asset.SerializeJson(true));
    Console.WriteLine("Exported authoring JSON: " + Path.GetFileName(args[2]));
    return;
}

if (args.Length >= 5 && args[0] == "clone")
{
    var source = Load(args[1]);
    var json = source.SerializeJson(false);
    var additions = new List<string>();
    for (var index = 3; index < args.Length; index++)
    {
        var pair = args[index].Split('=', 2);
        if (pair.Length != 2 || string.IsNullOrWhiteSpace(pair[0]))
            throw new ArgumentException("Each clone replacement must be OLD=NEW.");
        json = json.Replace(pair[0], pair[1], StringComparison.Ordinal);
        additions.Add(pair[1]);
    }

    // New package and class paths are FNames. Seed them in the serialized
    // name map before deserializing so UAssetAPI emits real references rather
    // than non-serializable dummy names.
    var document = JObject.Parse(json);
    var names = (JArray?)document["NameMap"] ?? throw new InvalidDataException("Missing asset NameMap.");
    foreach (var value in additions.Where(value => !names.Any(name => (string?)name == value)))
        names.Add(value);
    // Stock cosmetic replacements index the original hull's material slots.
    // An imported hull keeps its own cooked materials and has no compatible
    // stock skin layout. Clear only the component whose mesh resolves to an
    // imported Expanse package; leave native turret/effect components intact.
    var imports = document["Imports"]!.Children<JObject>().ToArray();
    foreach (var export in document["Exports"]!.Children<JObject>())
    {
        if (export["Data"] is not JArray properties) continue;
        var mesh = properties.Children<JObject>().FirstOrDefault(item => (string?)item["Name"] == "StaticMesh");
        if (mesh?["Value"]?.Type != JTokenType.Integer) continue;
        var meshIndex = mesh["Value"]!.Value<int>();
        if (meshIndex >= 0) continue;
        var meshImport = imports[-meshIndex - 1];
        var outer = meshImport["OuterIndex"]!.Value<int>();
        if (outer >= 0 || !((string?)imports[-outer - 1]["ObjectName"])!.StartsWith("/Game/Expanse/")) continue;
        foreach (var skin in properties.Children<JObject>().Where(item => (string?)item["Name"] == "Skins"))
        {
            if (skin["Value"] is JArray existing && existing.Count > 0)
                skin["DummyStruct"] = existing[0]!.DeepClone();
            skin["Value"] = new JArray();
        }
    }
    var cloned = UAsset.DeserializeJson(document.ToString());
    var destination = Path.GetFullPath(args[2]);
    Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
    cloned.Write(destination);
    var verified = Load(destination);
    Console.WriteLine("Wrote UE4.19 clone: " + Path.GetFileName(destination));
    Console.WriteLine("Reloaded exports: " + verified.Exports.Count + ", imports: " + verified.Imports.Count);
    return;
}

if (args.Length == 4 && args[0] == "drives")
{
    var document = JObject.Parse(Load(args[1]).SerializeJson(false));
    var points = JArray.Parse(File.ReadAllText(args[3]));
    void SetFlag(JArray data, string name, bool value)
    {
        var field = data.Children<JObject>().FirstOrDefault(item => (string?)item["Name"] == name);
        if (field is null)
        {
            field = new JObject { ["$type"] = "UAssetAPI.PropertyTypes.Objects.BoolPropertyData, UAssetAPI",
                ["Name"] = name, ["ArrayIndex"] = 0, ["PropertyGuid"] = null, ["IsZero"] = false,
                ["PropertyTagFlags"] = "None", ["PropertyTypeName"] = null, ["PropertyTagExtensions"] = "NoExtension" };
            data.Add(field);
        }
        field["Value"] = value;
        foreach (var required in new[] { name, "BoolProperty" })
            if (!document["NameMap"]!.Any(item => (string?)item == required)) ((JArray)document["NameMap"]!).Add(required);
    }
    var nativeScales = document["Exports"]!.Children<JObject>()
        .Where(item => ((string?)item["ObjectName"])!.StartsWith("ThrusterParticle") && item["Data"] is JArray)
        .SelectMany(item => item["Data"]!.Children<JObject>())
        .Where(item => (string?)item["Name"] == "RelativeScale3D")
        .Select(item => item["Value"]![0]!["Value"]!["X"]!.Value<double>()).OrderBy(value => value).ToArray();
    // Equal-sized source nozzles must not inherit the stock hull's mix of one
    // large central plume and several smaller auxiliary plumes.
    var plumeScale = nativeScales.Length == 0 ? 1.0 : nativeScales[nativeScales.Length / 2];
    var index = 0;
    foreach (var component in document["Exports"]!.Children<JObject>())
    {
        if (!((string?)component["ObjectName"])!.StartsWith("ThrusterParticle")) continue;
        if (component["Data"] is not JArray data) continue;
        var template = data.Children<JObject>().FirstOrDefault(item => (string?)item["Name"] == "Template");
        if (template is null) continue;
        var enabled = index < points.Count;
        SetFlag(data, "bAutoActivate", enabled);
        SetFlag(data, "bVisible", enabled);
        SetFlag(data, "bHiddenInGame", !enabled);
        if (!enabled) { template["Value"] = 0; continue; }
        var location = data.Children<JObject>().Single(item => (string?)item["Name"] == "RelativeLocation");
        var vector = (JObject)location["Value"]![0]!["Value"]!;
        for (var axis = 0; axis < 3; axis++) vector[new[] { "X", "Y", "Z" }[axis]] = points[index]![axis]!.Value<double>();
        if (points[index] is JArray pose)
        {
            var rotation = (JObject)location.DeepClone();
            rotation["Name"] = "RelativeRotation";
            rotation["StructType"] = "Rotator";
            var field = (JObject)rotation["Value"]![0]!;
            field["Name"] = "RelativeRotation";
            field["$type"] = "UAssetAPI.PropertyTypes.Structs.RotatorPropertyData, UAssetAPI";
            field["Value"] = new JObject { ["$type"] = "UAssetAPI.UnrealTypes.FRotator, UAssetAPI",
                ["Pitch"] = pose.Count == 6 ? pose[3]!.Value<double>() : 0,
                ["Yaw"] = pose.Count == 6 ? pose[4]!.Value<double>() : 0,
                ["Roll"] = pose.Count == 6 ? pose[5]!.Value<double>() : 0 };
            var oldRotation = data.Children<JObject>().FirstOrDefault(item => (string?)item["Name"] == "RelativeRotation");
            if (oldRotation is null) data.Add(rotation); else oldRotation.Replace(rotation);
            var names = (JArray)document["NameMap"]!;
            foreach (var required in new[] { "RelativeRotation", "Rotator" })
                if (!names.Any(name => (string?)name == required)) names.Add(required);
        }
        var scale = data.Children<JObject>().FirstOrDefault(item => (string?)item["Name"] == "RelativeScale3D");
        if (scale is null) { scale = (JObject)location.DeepClone(); scale["Name"] = "RelativeScale3D"; data.Add(scale); }
        scale["Value"]![0]!["Name"] = "RelativeScale3D";
        var scaleValue = (JObject)scale["Value"]![0]!["Value"]!;
        foreach (var axis in new[] { "X", "Y", "Z" }) scaleValue[axis] = plumeScale;
        if (!document["NameMap"]!.Any(name => (string?)name == "RelativeScale3D")) ((JArray)document["NameMap"]!).Add("RelativeScale3D");
        index++;
    }
    if (index != points.Count) throw new InvalidDataException($"Only mapped {index} of {points.Count} source nozzles.");
    // The source hull has its own emissive lamps. Stock skinned point lights
    // retain positions belonging to a different model and can glow in space.
    foreach (var component in document["Exports"]!.Children<JObject>())
    {
        if (!((string?)component["ObjectName"])!.StartsWith("SkinnedPointLight") || component["Data"] is not JArray data) continue;
        foreach (var property in data.Children<JObject>())
        {
            if ((string?)property["Name"] == "Intensity") property["Value"] = 0.0;
            if ((string?)property["Name"] == "Skins" && property["Value"] is JArray skins && skins.Count > 0)
            { property["DummyStruct"] = skins[0].DeepClone(); skins.Clear(); }
        }
        if (data.Children<JObject>().Any(item => (string?)item["Name"] == "Intensity"))
        {
            SetFlag(data, "bVisible", false);
            SetFlag(data, "bHiddenInGame", true);
        }
    }
    UAsset.DeserializeJson(document.ToString()).Write(Path.GetFullPath(args[2]));
    _ = Load(args[2]);
    Console.WriteLine("Mapped " + index + " native thrusters to reviewed source drive positions.");
    return;
}

if (args.Length == 4 && args[0] == "tune")
{
    var document = JObject.Parse(Load(args[1]).SerializeJson(false));
    var values = JObject.Parse(File.ReadAllText(args[3]));
    var cdo = document["Exports"]!.Children<JObject>().Single(item =>
        ((string?)item["ObjectName"])?.StartsWith("Default__", StringComparison.Ordinal) == true);
    var maxHealth = cdo["Data"]!.Children<JObject>().SingleOrDefault(item => (string?)item["Name"] == "MaxHealth");
    var oldHealth = maxHealth?["Value"]?.Value<double>();
    foreach (var requested in values.Properties())
    {
        var property = cdo["Data"]!.Children<JObject>().Single(item => (string?)item["Name"] == requested.Name);
        var value = requested.Value.Value<double>();
        if (!double.IsFinite(value) || value <= 0) throw new InvalidDataException("Invalid positive tuning value.");
        var type = (string?)property["$type"];
        if (type!.Contains("FloatPropertyData")) property["Value"] = value;
        else if (type.Contains("IntPropertyData") && value == Math.Truncate(value) && value <= int.MaxValue)
            property["Value"] = (int)value;
        else throw new InvalidDataException("Tuning requires an existing float or integer: " + requested.Name);
    }
    if (values.ContainsKey("MaxHealth"))
    {
        if (maxHealth is null || oldHealth is null || oldHealth <= 0) throw new InvalidDataException("Missing base hull health.");
        var healthRatio = maxHealth["Value"]!.Value<double>() / oldHealth.Value;
        foreach (var location in cdo["Data"]!.Children<JObject>().Where(item => (string?)item["Name"] == "LocationalDamage"))
        {
            foreach (var health in location["Value"]!.Children<JObject>().Where(item => (string?)item["Name"] == "Health"))
                health["Value"] = health["Value"]!.Value<double>() * healthRatio;
        }
    }
    UAsset.DeserializeJson(document.ToString()).Write(Path.GetFullPath(args[2]));
    _ = Load(args[2]);
    Console.WriteLine("Wrote and reloaded " + values.Count + " ship-data balance properties.");
    return;
}

if (args.Length == 4 && args[0] == "vectors")
{
    var source = Load(args[1]);
    var document = JObject.Parse(source.SerializeJson(false));
    var requested = JObject.Parse(File.ReadAllText(Path.GetFullPath(args[3])));
    var changed = 0;
    foreach (var export in document["Exports"]!.Children<JObject>())
    {
        var name = (string?)export["ObjectName"];
        if (name is null || requested[name] is not JArray vector || vector.Count != 3)
            continue;
        var location = export["Data"]?.Children<JObject>()
            .FirstOrDefault(item => (string?)item["Name"] == "RelativeLocation");
        if (location?["Value"] is not JArray fields)
            throw new InvalidDataException($"{name} has no editable RelativeLocation.");
        var field = fields.Children<JObject>().SingleOrDefault(item =>
            item["Value"] is JObject value && value.ContainsKey("X") && value.ContainsKey("Y") && value.ContainsKey("Z"))
            ?? throw new InvalidDataException($"{name} has no serialized FVector.");
        var coordinates = (JObject)field["Value"]!;
        coordinates["X"] = vector[0]!.Value<double>();
        coordinates["Y"] = vector[1]!.Value<double>();
        coordinates["Z"] = vector[2]!.Value<double>();
        changed++;
    }
    if (changed != requested.Count)
        throw new InvalidDataException($"Updated {changed} vector exports; expected {requested.Count}.");
    var edited = UAsset.DeserializeJson(document.ToString());
    var destination = Path.GetFullPath(args[2]);
    Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
    edited.Write(destination);
    _ = Load(destination);
    Console.WriteLine("Wrote " + changed + " adjusted attachment vectors.");
    return;
}

throw new ArgumentException("Usage: FleetAssetTool dump <local.uasset> <output.json> | clone <source.uasset> <destination.uasset> OLD=NEW [...] | vectors <source.uasset> <destination.uasset> <vectors.json>");
