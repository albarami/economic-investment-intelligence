import { MountedPublicShell } from './MountedPublicShell';

export const EXTRACT_URL = '/tiles/basemap.pmtiles';

export function App() {
  return <MountedPublicShell extractUrl={EXTRACT_URL} />;
}
