export function createPlaceSearch(poster) {
  let results = [];
  let camera = null;
  return {
    async search(text, lang) {
      const outcome = await poster(text, lang);
      if (!outcome || outcome.state === 'gazetteer_only') {
        results = [];
        camera = null;
        return { state: 'gazetteer_only' };
      }
      results = outcome.results ?? [];
      const first = results[0];
      camera = first
        ? {
            longitude: first.point.longitude,
            latitude: first.point.latitude,
          }
        : null;
      return {
        state: 'shown',
        label: first ? first.label : '',
        camera,
      };
    },
    close() {
      results = [];
      camera = null;
    },
    get results() {
      return results;
    },
    get camera() {
      return camera;
    },
  };
}
