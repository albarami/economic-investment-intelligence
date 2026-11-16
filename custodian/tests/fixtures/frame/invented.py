"""Hand-made equatorial polygons, never fetched geography."""

from shapely.geometry import box

from eii_custodian.publicdata.frame.geometry import Boundary


def invented_frame():
    # Arbitrary equatorial squares, not Qatar polygons.
    whole = box(0, 0, 0.04, 0.04)
    left = box(0, 0, 0.02, 0.04)
    right = box(0.02, 0, 0.04, 0.04)

    def boundary(key, shape, municipality):
        return Boundary(key, "Invented " + key, "اسم تجريبي", municipality, shape)

    municipalities = [boundary("SYN-A", whole, "SYN-A")]
    zones = [boundary("SYN-Z", whole, "SYN-A")]
    districts = [boundary("SYN-D", left, "SYN-A"), boundary("SYN-E", right, "SYN-A")]
    return municipalities, zones, districts


def invented_geob_metadata():
    """Metadata shape supplied by the lead; every value is invented text."""
    return {
        name: "Invented metadata"
        for name in (
            "boundaryID",
            "boundaryName",
            "boundaryISO",
            "boundaryYearRepresented",
            "boundaryType",
            "boundaryCanonical",
            "boundarySource",
            "boundaryLicense",
            "licenseDetail",
            "licenseSource",
            "boundarySourceURL",
            "sourceDataUpdateDate",
            "buildDate",
            "Continent",
            "UNSDG-region",
            "UNSDG-subregion",
            "worldBankIncomeGroup",
            "admUnitCount",
            "meanVertices",
            "minVertices",
            "maxVertices",
            "meanPerimeterLengthKM",
            "minPerimeterLengthKM",
            "maxPerimeterLengthKM",
            "meanAreaSqKM",
            "minAreaSqKM",
            "maxAreaSqKM",
            "staticDownloadLink",
            "gjDownloadURL",
            "tjDownloadURL",
            "imagePreview",
            "simplifiedGeometryGeoJSON",
        )
    }


def invented_layer(source):
    common = {
        "ZONE_NO": 42,
        "MUNICIPAL_CODE": "9",
        "OBJECTID": 17,
        "Shape__Area": 0.1,
        "Shape__Length": 0.2,
    }
    specifics = {
        "bnd_zone_2020": {
            "Municipality_En": "Different invented spelling",
            "Municipality_Ar": "اسم تجريبي",
            "Mun_code2": None,
        },
        "census_zone_sector": {
            "Muni_Name": "Invented",
            "Total_Economic_active___15": 17,
            "Government": None,
            "Government_Establishment_Compan": 2,
            "Mixed": 3,
            "Private": 4,
            "Diplomatic_Iinternational_Regio": 1,
            "Non_Profit": 0,
            "Household": 7,
        },
        "census_zone_occ": {
            "Muni_Name": "Invented",
            "Pop_Aged__above__15": 17,
            "Legislators_Senior_Officials_An": 0,
            "Professionals": 1,
            "Technicians_And_Associate_Profe": 2,
            "Clerks": 3,
            "Service_Workers_And_Shop_And_Ma": 4,
            "Skilled_Agricultural_And_Fisher": 1,
            "Craft_And_Related_Trades_Worker": 0,
            "Plant_And_Machine_Operators_And": 2,
            "Elementary_Occupations": 3,
            "Other": 1,
        },
        "census_zone_hh": {"Qatari": None, "Non_Qatari": 17},
        "census_zone_lab": {"labor_gathering": None, "Small_gathering": 17},
    }
    if source in specifics:
        attrs = {**common, **specifics[source]}
    elif source == "bnd_district_2020":
        attrs = {
            "DIST_NO": 73,
            "DIST_KEY": 73,
            "KEY_NO": 42,
            "ENAME": "Invented district",
            "ANAME": "اسم تجريبي",
            "Area_SQKM": 0.2,
            "Density_pop": None,
            "GLOBALID": "SYN-G",
            "Field": None,
            "OBJECTID": 17,
            "Shape__Area": 0.1,
            "Shape__Length": 0.2,
        }
    elif source == "census_district_pop":
        attrs = {
            "ZONENO": 42,
            "DISTRICTNO": 73,
            "POP2020": 17,
            "OBJECTID": 17,
            "Shape__Area": 0.1,
            "Shape__Length": 0.2,
        }
    else:
        raise AssertionError(source)
    return {
        "count": 1,
        "features": [
            {
                "attributes": attrs,
                "geometry": {
                    "rings": [[[900, 900], [901, 900], [900, 901], [900, 900]]]
                },
            }
        ],
    }


def invented_archive():
    import io
    import json
    import zipfile

    from shapely.geometry import mapping

    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for level in (1, 2, 3):
            props = {
                "valid_on": "2026-01-01",
                "valid_to": None,
                "version": "invented",
                "lang": "en",
                "lang1": "ar",
                "lang2": None,
                "lang3": None,
                "area_sqkm": 1.0,
                "center_lon": 0.02,
                "center_lat": 0.02,
            }
            for n in range(level + 1):
                props.update(
                    {
                        f"adm{n}_name": "Invented municipality",
                        f"adm{n}_name1": "اسم تجريبي",
                        f"adm{n}_name2": None,
                        f"adm{n}_name3": None,
                        f"adm{n}_pcode": "SYN" + "042" * n,
                    }
                )
            if level >= 2:
                props["adm2_name"] = "Invented zone 42"
            if level == 3:
                props["adm3_name"] = "Invented district"
            document = {
                "type": "FeatureCollection",
                "name": "Invented",
                "crs": {
                    "type": "name",
                    "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
                },
                "features": [
                    {
                        "type": "Feature",
                        "properties": props,
                        "geometry": mapping(box(0, 0, 0.04, 0.04)),
                    }
                ],
            }
            # A fixed member time keeps the bytes off the clock: a caller may
            # build the archive twice and compare hashes.
            member = zipfile.ZipInfo(
                f"qat_admin{level}.geojson", date_time=(1980, 1, 1, 0, 0, 0)
            )
            member.external_attr = 0o600 << 16
            member.compress_type = zipfile.ZIP_STORED
            archive.writestr(member, json.dumps(document))
    return stream.getvalue()
