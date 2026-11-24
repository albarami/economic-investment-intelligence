/** Display families have no rank, criterion, weight, blend or chart input. */
export const contextFamilies = {
  night_lights: {
    metric: 'night_lights_radiance',
    unit: 'radiance_nw_cm2_sr',
    table: 'pub_night_lights',
    caveat: 'night_lights_not_activity',
    subject: 'area',
    geography: 'area_shape',
    label: 'Night-time radiance',
    comparison: 'context_compare_night_lights',
  },
  venue_busyness: {
    metric: 'venue_busyness_index',
    unit: 'relative_index',
    table: 'pub_venue_busyness',
    caveat: 'relative_busyness_not_people',
    subject: 'place_public',
    geography: 'public',
    label: 'BestTime relative busyness',
    comparison: 'context_compare_venue_busyness',
  },
  population_age_sex: {
    metric: 'population_grid_people',
    unit: 'count',
    table: 'pub_pop_agesex_grid',
    caveat: 'grid_cells_summed',
    subject: 'area',
    geography: 'area_shape',
    label: 'Population by age and sex',
    comparison: 'context_compare_population_age_sex',
  },
} as const;

export type ContextFamily = keyof typeof contextFamilies;
