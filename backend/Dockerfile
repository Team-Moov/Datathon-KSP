FROM python:3.11-slim

# No apt-get system packages needed anymore. This used to install gcc,
# libpq-dev, libgdal-dev, libgeos-dev, and ffmpeg — but geopandas/shapely
# (the only reason for GDAL/GEOS) and ffmpeg were never actually imported or
# shelled out to anywhere in the codebase (confirmed by grep), and
# psycopg2-binary's prebuilt wheel bundles its own libpq, so gcc/libpq-dev
# weren't needed either — this was the single largest chunk of the image
# (GDAL alone transitively pulls in boost, ICU, spatialite, xerces-c,
# proj-data). If a future `pip install` here ever fails needing to compile a
# package from source, gcc is the first thing to add back.

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
