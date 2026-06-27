import { useCallback, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet-draw';
import 'leaflet-draw/dist/leaflet.draw.css';
import turfArea from '@turf/area';

/* Fix Leaflet default marker icons */
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

/* ── Converts m² → hectares ── */
function sqmToHa(sqm) {
  return +(sqm / 10000).toFixed(2);
}

/* ── Leaflet Draw controller ── */
function DrawControls({ existingGeoJson, onGeoJsonChange }) {
  const map = useMap();
  const drawnRef = useRef(new L.FeatureGroup());
  const controlRef = useRef(null);

  /* Initialise draw controls once */
  useEffect(() => {
    const drawnItems = drawnRef.current;
    map.addLayer(drawnItems);

    const drawControl = new L.Control.Draw({
      position: 'topright',
      draw: {
        polygon: {
          allowIntersection: false,
          showArea: true,
          shapeOptions: {
            color: '#22c55e',
            weight: 2,
            fillOpacity: 0.15,
          },
        },
        rectangle: {
          shapeOptions: {
            color: '#22c55e',
            weight: 2,
            fillOpacity: 0.15,
          },
        },
        polyline: false,
        circle: false,
        circlemarker: false,
        marker: false,
      },
      edit: {
        featureGroup: drawnItems,
        remove: true,
      },
    });

    controlRef.current = drawControl;
    map.addControl(drawControl);

    /* Handle draw events */
    map.on(L.Draw.Event.CREATED, (e) => {
      drawnItems.clearLayers();
      drawnItems.addLayer(e.layer);
      emitGeoJson(drawnItems);
    });

    map.on(L.Draw.Event.EDITED, () => emitGeoJson(drawnItems));
    map.on(L.Draw.Event.DELETED, () => emitGeoJson(drawnItems));

    return () => {
      map.removeControl(drawControl);
      map.removeLayer(drawnItems);
      map.off(L.Draw.Event.CREATED);
      map.off(L.Draw.Event.EDITED);
      map.off(L.Draw.Event.DELETED);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map]);

  /* Load existing GeoJSON onto the map */
  useEffect(() => {
    if (!existingGeoJson) return;
    const drawnItems = drawnRef.current;
    drawnItems.clearLayers();

    try {
      const layer = L.geoJSON(existingGeoJson, {
        style: { color: '#22c55e', weight: 2, fillOpacity: 0.15 },
      });
      layer.eachLayer((l) => drawnItems.addLayer(l));

      const bounds = drawnItems.getBounds();
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
      }
    } catch {
      /* invalid geojson - skip */
    }
  }, [existingGeoJson, map]);

  /* Emit GeoJSON + computed area */
  const emitGeoJson = useCallback(
    (featureGroup) => {
      if (featureGroup.getLayers().length === 0) {
        onGeoJsonChange?.(null, 0);
        return;
      }

      const geojson = featureGroup.toGeoJSON();
      const areaM2 = turfArea(geojson);
      const areaHa = sqmToHa(areaM2);
      onGeoJsonChange?.(geojson, areaHa);
    },
    [onGeoJsonChange],
  );

  return null;
}

/**
 * DrawableMap — an interactive satellite map with polygon draw tools.
 *
 * Props:
 *  - existingGeoJson  (object | null) : pre-fill drawn shape
 *  - onGeoJsonChange  (geojson, areaHa) => void
 *  - height           (number | string) : map height (default 460)
 *  - center           ([lat, lng])
 *  - zoom             (number)
 */
function DrawableMap({
  existingGeoJson = null,
  onGeoJsonChange,
  height = 460,
  center = [22.5, 79.0],
  zoom = 5,
}) {
  return (
    <MapContainer
      center={center}
      zoom={zoom}
      style={{ height, width: '100%', borderRadius: 12 }}
      scrollWheelZoom
    >
      {/* Satellite basemap (Esri) — free, no API key */}
      <TileLayer
        url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        attribution="Tiles &copy; Esri"
        maxZoom={19}
      />
      {/* Labels overlay */}
      <TileLayer
        url="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
        maxZoom={19}
      />
      <DrawControls
        existingGeoJson={existingGeoJson}
        onGeoJsonChange={onGeoJsonChange}
      />
    </MapContainer>
  );
}

export default DrawableMap;
