import type { PickingInfo } from '@deck.gl/core'
import { MapboxOverlay, type MapboxOverlayProps } from '@deck.gl/mapbox'
import Box from '@mui/material/Box'
import Paper from '@mui/material/Paper'
import { useColorScheme } from '@mui/material/styles'
import Typography from '@mui/material/Typography'
import useMediaQuery from '@mui/material/useMediaQuery'
import 'maplibre-gl/dist/maplibre-gl.css'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import { useEffect, useMemo, useRef, useState } from 'react'
import Map, {
  AttributionControl,
  NavigationControl,
  useControl,
  type MapRef,
} from 'react-map-gl/maplibre'
import type { TripPlan } from '@/api/schemas'
import { ForecastControls } from './ForecastControls'
import {
  buildHeatmapGrid,
  checkpointLayer,
  decodeRoutes,
  endpointLayer,
  heatmapFade,
  heatmapLayer,
  heatmapRadiusPixels,
  pathBounds,
  routeLayers,
  targetFromPick,
  type DecodedRoute,
  type Scheme,
} from './layers'
import { MapTooltip, type MapTooltipHandle, type TooltipPosition } from './MapTooltip'
import { clickIntent, type LngLat } from './tooltipState'
import { usePlanForecast } from './usePlanForecast'

interface TripMapProps {
  plan: TripPlan | null
  selectedRouteId: string | null
  onSelectRoute: (id: string) => void
}

const MAP_STYLES: Record<Scheme, string> = {
  light: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
  dark: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
}

const INITIAL_VIEW = { longitude: -96, latitude: 38.5, zoom: 3.4 }

// Overlaid rather than interleaved: deck 9.4's interleaved renderer reads `map.transform`,
// which maplibre 6 no longer exposes. Overlaid mode redraws in the same frame on map render.
function DeckOverlay({ props }: { props: MapboxOverlayProps }) {
  const overlay = useControl(() => new MapboxOverlay({ ...props, interleaved: false }))
  useEffect(() => {
    overlay.setProps(props)
  }, [overlay, props])
  return null
}

function useScheme(): Scheme {
  const { mode, systemMode } = useColorScheme()
  const prefersDark = useMediaQuery('(prefers-color-scheme: dark)')
  const resolved = mode === 'system' ? systemMode : mode
  return resolved ?? (prefersDark ? 'dark' : 'light')
}

export function TripMap({ plan, selectedRouteId, onSelectRoute }: TripMapProps) {
  const scheme = useScheme()
  const reduceMotion = useMediaQuery('(prefers-reduced-motion: reduce)')
  const mapRef = useRef<MapRef>(null)
  const controlsRef = useRef<HTMLDivElement>(null)
  const tooltipRef = useRef<MapTooltipHandle>(null)
  const [mapReady, setMapReady] = useState(false)
  const [heatmapOn, setHeatmapOn] = useState(true)
  const [view, setView] = useState({ zoom: INITIAL_VIEW.zoom, radiusPixels: 40 })

  const { hour, setHour, metric, setMetric, maxHour, planKey } = usePlanForecast(plan)
  const desktop = useMediaQuery((theme) => theme.breakpoints.up('md'))
  const pointerType = useRef<string | null>(null)
  const fade = heatmapFade(view.zoom)

  const routes = useMemo(() => (plan ? decodeRoutes(plan.routes) : []), [plan])
  const grid = useMemo(() => (plan ? buildHeatmapGrid(plan.heatmap) : null), [plan])

  const staticLayers = useMemo(() => {
    if (!plan) return []
    const selected = routes.find((r) => r.id === selectedRouteId) ?? routes[0]
    return [
      ...routeLayers(routes, selectedRouteId, scheme),
      checkpointLayer(plan.routes, selectedRouteId, scheme),
      endpointLayer(selected, scheme),
    ]
  }, [plan, routes, selectedRouteId, scheme])

  const heat = useMemo(
    () =>
      grid &&
      heatmapLayer(grid, hour, metric, {
        visible: heatmapOn,
        radiusPixels: view.radiusPixels,
        scheme,
        fade,
      }),
    [grid, hour, metric, heatmapOn, view.radiusPixels, scheme, fade],
  )

  const gridDeg = plan?.weather_grid_deg
  const updateView = () => {
    const map = mapRef.current
    if (!map) return
    const zoom = map.getZoom()
    setView({
      zoom: Math.round(zoom * 10) / 10,
      radiusPixels: Math.round(heatmapRadiusPixels(zoom, map.getCenter().lat, gridDeg)),
    })
  }

  // The heatmap rebuilds its weight texture on radius change but does not ask for a frame.
  useEffect(() => {
    mapRef.current?.triggerRepaint()
  }, [view.radiusPixels])

  const fitted = useRef<{ plan: TripPlan | null; routeId: string | null }>({
    plan: null,
    routeId: null,
  })

  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady || !plan) return
    const last = fitted.current
    let target: DecodedRoute['path'] | undefined
    if (last.plan !== plan) {
      target = routes.flatMap((r) => r.path)
      fitted.current = { plan, routeId: plan.recommended_route_id }
    } else if (selectedRouteId !== last.routeId) {
      target = routes.find((r) => r.id === selectedRouteId)?.path
      fitted.current = { plan, routeId: selectedRouteId }
    }
    if (!target?.length) return
    const panel = controlsRef.current?.offsetHeight ?? 0
    map.fitBounds(pathBounds(target), {
      padding: { top: 48, left: 48, right: 48, bottom: panel + 40 },
      duration: reduceMotion ? 0 : 700,
    })
  }, [plan, routes, selectedRouteId, mapReady, reduceMotion])

  const overlayProps = useMemo<MapboxOverlayProps>(() => {
    // Keep tooltips clear of the forecast panel, which sits over the bottom of the map.
    const positionOf = (info: PickingInfo): TooltipPosition => ({
      x: info.x,
      y: info.y,
      width: info.viewport?.width ?? 0,
      height: (info.viewport?.height ?? 0) - (controlsRef.current?.offsetHeight ?? 0),
    })
    return {
      layers: heat ? [heat, ...staticLayers] : staticLayers,
      pickingRadius: 6,
      onHover: (info: PickingInfo) => {
        const canvas = mapRef.current?.getCanvas()
        if (canvas) canvas.style.cursor = info.picked ? 'pointer' : ''
        tooltipRef.current?.send({ type: 'hover', target: targetFromPick(info) }, positionOf(info))
      },
      onClick: (info: PickingInfo) => {
        const intent = clickIntent(targetFromPick(info), pointerType.current)
        if (intent.tooltip) {
          const [lng, lat] = info.coordinate ?? []
          const anchor: LngLat | undefined =
            lng !== undefined && lat !== undefined ? [lng, lat] : undefined
          tooltipRef.current?.send(intent.tooltip, positionOf(info), anchor)
        }
        if (intent.selectRouteId) onSelectRoute(intent.selectRouteId)
      },
    }
  }, [heat, staticLayers, onSelectRoute])

  return (
    <Box
      sx={{ position: 'absolute', inset: 0, overflow: 'hidden' }}
      onPointerDownCapture={(e) => {
        pointerType.current = e.pointerType
      }}
    >
      <Map
        ref={mapRef}
        initialViewState={INITIAL_VIEW}
        mapStyle={MAP_STYLES[scheme]}
        // maplibre resolves its worker relative to its own module, which Vite's bundling breaks
        workerUrl={workerUrl}
        attributionControl={false}
        dragRotate={false}
        touchPitch={false}
        style={{ position: 'absolute', inset: 0 }}
        onLoad={() => {
          setMapReady(true)
          updateView()
        }}
        onZoomEnd={updateView}
        onMove={() => {
          const map = mapRef.current
          if (!map) return
          const canvas = map.getCanvas()
          tooltipRef.current?.follow((p) => map.project(p), {
            width: canvas.clientWidth,
            height: canvas.clientHeight - (controlsRef.current?.offsetHeight ?? 0),
          })
        }}
        onMoveStart={(e) => {
          // Only user gestures dismiss a pinned tooltip; fitting to a selected route should not.
          if (e.originalEvent) tooltipRef.current?.send({ type: 'clear' })
        }}
      >
        <AttributionControl position="top-right" compact />
        {desktop ? <NavigationControl position="top-left" showCompass={false} /> : null}
        <DeckOverlay props={overlayProps} />
      </Map>

      {plan ? (
        <>
          <MapTooltip key={planKey} ref={tooltipRef} plan={plan} />
          <ForecastControls
            ref={controlsRef}
            start={plan.heatmap.start}
            hour={hour}
            maxHour={maxHour}
            onHourChange={setHour}
            metric={metric}
            onMetricChange={setMetric}
            scheme={scheme}
            heatmapOn={heatmapOn}
            onHeatmapChange={setHeatmapOn}
            heatmapFaded={fade === 0}
          />
        </>
      ) : (
        <Paper
          elevation={0}
          sx={{
            position: 'absolute',
            top: 16,
            left: '50%',
            transform: 'translateX(-50%)',
            px: 2,
            py: 1,
            border: 1,
            borderColor: 'divider',
            maxWidth: 'calc(100% - 32px)',
          }}
        >
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            Plan a trip to see routes and forecast risk here.
          </Typography>
        </Paper>
      )}
    </Box>
  )
}
