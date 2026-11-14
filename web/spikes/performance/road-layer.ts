import { PathLayer } from '@deck.gl/layers';
import {
  PathStyleExtension,
  type PathStyleExtensionProps,
} from '@deck.gl/extensions';
import {
  ROAD_COLORS,
  ROAD_DASH,
  ROAD_WIDTHS,
  VOLUME_BANDS,
} from './config.mjs';
import { bandAt, type Road } from './roads.mjs';

const extension = new PathStyleExtension({ dash: true });
export function roadLayer(
  roads: Road[],
  hour: number,
  opacity: number,
  slot: number,
  plant: string,
) {
  return new PathLayer<Road, PathStyleExtensionProps<Road>>({
    id: `simulated-roads-${slot}`,
    data: roads,
    getPath: (road) => road.path,
    getWidth: (road) => ROAD_WIDTHS[road.roadClass]!,
    widthUnits: 'pixels',
    getColor: (road) => ROAD_COLORS[VOLUME_BANDS.indexOf(bandAt(road, hour))]!,
    updateTriggers: { getColor: hour },
    opacity,
    extensions: plant === 'omit-road-dash' ? [] : [extension],
    getDashArray: ROAD_DASH,
    dashJustified: true,
    dashGapPickable: false,
    visible: plant !== 'hide-roads' && opacity > 0,
  });
}
