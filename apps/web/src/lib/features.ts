// Add only routes whose backend contract is not yet implemented. Career/HR routes
// are now supplied by the separately integrated AI adapter.
const plannedRoutes: RegExp[] = [];
export const DEVELOPMENT_NOTICE = 'Раздел в разработке. Он появится после подключения расчётов и рекомендаций.';
export function isPlannedRoute(path: string): boolean {
  return plannedRoutes.some(pattern => pattern.test(path));
}
