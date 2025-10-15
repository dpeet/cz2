/**
 * Toaster Component using Sonner
 *
 * Provides toast notifications for the application with custom icons
 * and styling adapted for the HVAC thermostat interface.
 */

import {
  CircleCheckIcon,
  InfoIcon,
  Loader2Icon,
  OctagonXIcon,
  TriangleAlertIcon,
} from "lucide-react";
import { Toaster as Sonner } from "sonner";
import "./toaster.css";

export const Toaster = ({ ...props }) => {
  return (
    <Sonner
      theme="light"
      className="toaster"
      position="top-right"
      expand={false}
      richColors={true}
      closeButton={true}
      duration={5000}
      icons={{
        success: <CircleCheckIcon className="toast-icon" size={20} />,
        info: <InfoIcon className="toast-icon" size={20} />,
        warning: <TriangleAlertIcon className="toast-icon" size={20} />,
        error: <OctagonXIcon className="toast-icon" size={20} />,
        loading: <Loader2Icon className="toast-icon toast-icon-spin" size={20} />,
      }}
      {...props}
    />
  );
};
