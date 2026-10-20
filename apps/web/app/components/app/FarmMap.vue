<script setup lang="ts">
import { Map as MapLibreMap, NavigationControl, setWorkerUrl } from 'maplibre-gl'
import type { GeoJSONSource, LngLatBoundsLike } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { LAND_USE_CATEGORIES, landUseColor } from '~/utils/land-use'
import type { LandUseCategory } from '~/utils/land-use'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'

// MapLibre derives its worker location from its own module URL, which bundling breaks;
// shipping the worker as an asset works the same in dev and in production builds.
setWorkerUrl(workerUrl)

// Deliberately narrow: any GeoJSON MultiPolygon features with an id and a Land Use code.
interface AreaFeature {
  type: 'Feature'
  id: string
  geometry: { type: 'MultiPolygon', coordinates: number[][][][] }
  properties: { land_use_category?: LandUseCategory } & Record<string, unknown>
}
interface AreaCollection {
  type: 'FeatureCollection'
  features: AreaFeature[]
}

const props = withDefaults(defineProps<{
  plots: AreaCollection
  fields?: AreaCollection | null
  selectedId?: string | null
  hoveredId?: string | null
}>(), { fields: null, selectedId: null, hoveredId: null })

const emit = defineEmits<{
  hover: [id: string | null]
  select: [id: string]
}>()

const { t } = useI18n()

const legend = computed(() => {
  const present = new Set(props.plots.features.map(f => f.properties.land_use_category ?? 'other'))
  return LAND_USE_CATEGORIES.filter(category => present.has(category))
})
const container = useTemplateRef<HTMLDivElement>('container')
const basemap = ref<'ortho' | 'map'>('ortho')
let map: MapLibreMap | null = null
// Sources and layers exist only after `load`; updates before that are applied on load.
let ready = false

const BASEMAP_ATTRIBUTION = '<a href="https://basemap.at" target="_blank" rel="noopener">basemap.at</a>'
const AREAS_ATTRIBUTION = 'Feldstücke/Schläge: AMA INVEKOS'
// basemap.at covers Austria only; outside it every tile request would be a 404.
const AUSTRIA: [number, number, number, number] = [9.4, 46.3, 17.2, 49.1]

function plotData() {
  return {
    type: 'FeatureCollection' as const,
    features: props.plots.features.map(feature => ({
      ...feature,
      properties: { ...feature.properties, color: landUseColor(feature.properties.land_use_category ?? 'other') }
    }))
  }
}

function fieldData() {
  return props.fields ?? { type: 'FeatureCollection' as const, features: [] }
}

function bounds(): LngLatBoundsLike | null {
  let west = Infinity, south = Infinity, east = -Infinity, north = -Infinity
  for (const feature of props.plots.features) {
    for (const polygon of feature.geometry.coordinates) {
      for (const ring of polygon) {
        for (const position of ring) {
          const lon = position[0]!
          const lat = position[1]!
          west = Math.min(west, lon)
          east = Math.max(east, lon)
          south = Math.min(south, lat)
          north = Math.max(north, lat)
        }
      }
    }
  }
  return Number.isFinite(west) ? [[west, south], [east, north]] : null
}

function fit(animate: boolean) {
  const box = bounds()
  if (map && ready && box) map.fitBounds(box, { padding: 48, maxZoom: 17, animate })
}

function setState(id: string | null | undefined, key: 'hover' | 'selected', value: boolean) {
  if (map && ready && id) map.setFeatureState({ source: 'plots', id }, { [key]: value })
}

onMounted(() => {
  const instance = new MapLibreMap({
    container: container.value!,
    attributionControl: { compact: true },
    style: {
      version: 8,
      sources: {
        ortho: {
          type: 'raster',
          tiles: ['https://mapsneu.wien.gv.at/basemap/bmaporthofoto30cm/normal/google3857/{z}/{y}/{x}.jpeg'],
          tileSize: 256,
          maxzoom: 19,
          bounds: AUSTRIA,
          attribution: BASEMAP_ATTRIBUTION
        },
        map: {
          type: 'raster',
          tiles: ['https://mapsneu.wien.gv.at/basemap/geolandbasemap/normal/google3857/{z}/{y}/{x}.png'],
          tileSize: 256,
          maxzoom: 19,
          bounds: AUSTRIA,
          attribution: BASEMAP_ATTRIBUTION
        }
      },
      layers: [
        { id: 'ortho', type: 'raster', source: 'ortho' },
        { id: 'map', type: 'raster', source: 'map', layout: { visibility: 'none' } }
      ]
    },
    center: [13.3, 47.6],
    zoom: 6.5
  })
  instance.addControl(new NavigationControl({ showCompass: false }), 'top-right')
  map = instance

  instance.on('load', () => {
    const map = instance
    map.addSource('fields', { type: 'geojson', data: fieldData() })
    map.addSource('plots', {
      type: 'geojson',
      data: plotData(),
      promoteId: 'id',
      attribution: AREAS_ATTRIBUTION
    })
    map.addLayer({
      id: 'plots-fill',
      type: 'fill',
      source: 'plots',
      paint: {
        'fill-color': ['get', 'color'],
        'fill-opacity': ['case',
          ['boolean', ['feature-state', 'selected'], false], 0.7,
          ['boolean', ['feature-state', 'hover'], false], 0.6,
          0.38]
      }
    })
    map.addLayer({
      id: 'plots-line',
      type: 'line',
      source: 'plots',
      paint: {
        'line-color': ['case',
          ['boolean', ['feature-state', 'selected'], false], '#f5f2e9',
          ['boolean', ['feature-state', 'hover'], false], '#f5f2e9',
          ['get', 'color']],
        'line-width': ['case',
          ['boolean', ['feature-state', 'selected'], false], 3,
          ['boolean', ['feature-state', 'hover'], false], 3,
          1.5]
      }
    })
    map.addLayer({
      id: 'fields-line',
      type: 'line',
      source: 'fields',
      paint: { 'line-color': '#f5f2e9', 'line-width': 1.5, 'line-dasharray': [2, 1.5] }
    })

    map.on('mousemove', 'plots-fill', (event) => {
      const id = event.features?.[0]?.id
      map.getCanvas().style.cursor = 'pointer'
      emit('hover', typeof id === 'string' ? id : null)
    })
    map.on('mouseleave', 'plots-fill', () => {
      map.getCanvas().style.cursor = ''
      emit('hover', null)
    })
    map.on('click', 'plots-fill', (event) => {
      const id = event.features?.[0]?.id
      if (typeof id === 'string') emit('select', id)
    })

    ready = true
    applyBasemap(basemap.value)
    setState(props.selectedId, 'selected', true)
    setState(props.hoveredId, 'hover', true)
    fit(false)
  })
})

onBeforeUnmount(() => {
  ready = false
  map?.remove()
  map = null
})

function applyBasemap(choice: 'ortho' | 'map') {
  if (!map || !ready) return
  map.setLayoutProperty('ortho', 'visibility', choice === 'ortho' ? 'visible' : 'none')
  map.setLayoutProperty('map', 'visibility', choice === 'map' ? 'visible' : 'none')
}

watch(() => props.plots, () => {
  if (!ready) return
  (map?.getSource('plots') as GeoJSONSource | undefined)?.setData(plotData())
  fit(true)
})
watch(() => props.fields, () => {
  if (!ready) return
  (map?.getSource('fields') as GeoJSONSource | undefined)?.setData(fieldData())
})
watch(() => props.hoveredId, (now, before) => {
  setState(before, 'hover', false)
  setState(now, 'hover', true)
})
watch(() => props.selectedId, (now, before) => {
  setState(before, 'selected', false)
  setState(now, 'selected', true)
})
watch(basemap, applyBasemap)
</script>

<template>
  <div class="relative size-full overflow-hidden rounded-lg border border-default">
    <div
      ref="container"
      class="size-full"
      data-testid="farm-map"
    />
    <div class="absolute top-2.5 left-2.5 flex rounded-full border border-default bg-default/90 p-0.5 text-xs shadow-sm backdrop-blur">
      <button
        v-for="option in (['ortho', 'map'] as const)"
        :key="option"
        type="button"
        class="rounded-full px-2.5 py-1 font-medium transition-colors"
        :class="basemap === option ? 'bg-elevated text-highlighted' : 'text-muted hover:text-highlighted'"
        :aria-pressed="basemap === option"
        @click="basemap = option"
      >
        {{ t(`app.map.${option}`) }}
      </button>
    </div>
    <ul
      v-if="legend.length"
      class="absolute bottom-2.5 left-2.5 space-y-1 rounded-lg border border-default bg-default/90 px-2.5 py-2 text-xs shadow-sm backdrop-blur"
      :aria-label="t('app.map.legend')"
    >
      <li
        v-for="category in legend"
        :key="category"
        class="flex items-center gap-2"
      >
        <span
          class="size-2.5 rounded-sm"
          :style="{ backgroundColor: landUseColor(category) }"
          aria-hidden="true"
        />
        {{ t(`app.landUseCategory.${category}`) }}
      </li>
    </ul>
  </div>
</template>
