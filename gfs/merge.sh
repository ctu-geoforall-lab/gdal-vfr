#!/bin/sh

# Merge GFS files for GDAL

merge() {
    ST_FILE="vfr_st_v1.gfs"
    rm -f $ST_FILE
    echo "<GMLFeatureClassList>" > $ST_FILE

    for f in $2; do
        cat ${f}.gfs | tail -n +2 | head -n -1 >> $ST_FILE
    done
    echo "</GMLFeatureClassList>" >> $ST_FILE
}

merge "vfr_st_v1.gfs" "Staty" \
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

exit 0