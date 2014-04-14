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

FILE="vfr_st_v1.gfs"
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

FILE="vfr_ob_v1.gfs"
merge "Obce" \
    "CastiObci" \
    "KatastralniUzemi" \
    "Zsj" \
    "Ulice" \
    "Parcely" \
    "StavebniObjekty" \
    "AdresniMista"

exit 0