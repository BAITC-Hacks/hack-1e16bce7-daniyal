'use client';

import { EmployeeProfile } from '../components/employee-profile';
import { Workspace, useSession } from '../components/workspace';

export default function Home() {
  const { user } = useSession();
  return <Workspace>{user?.role === 'employee' && user.employee_id && <EmployeeProfile key={user.employee_id} employeeId={user.employee_id} />}</Workspace>;
}
