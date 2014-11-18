#!/bin/sh

# Merge GFS files for GDAL

merge() {
    rm -f $FILE
    echo "<GMLFeatureClassList>" > $FILE

    for f in "$@"; do
        echo "$f..."
        cat ${f}.gfs | tail -n +2 | head -n -1 >> $FILE
    done
    echo "</GMLFeatureClassList>" >> $FILE
}

merge_st() {
    FILE="ruian_vf_st_v1.gfs"
    merge "Staty" \
        "RegionySoudrznosti" \
        "Kraje" \
        "Vusc" \
        "Okresy" \
        "Orp" \
        "Pou" \
        "Obce" \
        "SpravniObvody" \
        "Mop" \
        "Momc" \
        "CastiObci" \
        "KatastralniUzemi" \
        "Zsj"
}

merge_ob() {
    FILE="ruian_vf_ob_v1.gfs"
    merge "Obce" \
        "SpravniObvody" \
        "Mop" \
        "Momc" \
        "CastiObci" \
        "KatastralniUzemi" \
        "Zsj" \
        "Ulice" \
        "Parcely" \
        "StavebniObjekty" \
        "AdresniMista"
}

merge_all() {
    FILE="ruian_vf_v1.gfs"
    merge "Staty" \
        "RegionySoudrznosti" \
        "Kraje" \
        "Vusc" \
        "Okresy" \
        "Orp" \
        "Pou" \
        "Obce" \
        "SpravniObvody" \
        "Mop" \
        "Momc" \
        "CastiObci" \
        "KatastralniUzemi" \
        "Zsj" \
        "Ulice" \
        "Parcely" \
        "StavebniObjekty" \
        "AdresniMista" \
        "ZaniklePrvky"
}

merge_st
merge_ob
merge_all

exit 0
