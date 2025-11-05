/**
 * Tooltip content for HVAC controls
 * Based on the Carrier Comfort Zone II Owner's Manual
 *
 * This centralized file makes it easy to update tooltip text
 * without modifying component code.
 */

export const tooltipContent = {
  /**
   * System Mode Selection
   * Reference: Manual pages 13, 16
   */
  mode: {
    title: "System Mode",
    description: `Select the operating mode for your HVAC system:

• OFF — No mode selected, system is off
• HEAT — Heating only
• COOL — Cooling only
• AUTO — System will heat or cool as needed
• EHEAT — Emergency heat (heat pump systems only)

Changes take effect immediately and apply system-wide.`
  },

  /**
   * Fan Mode
   * Reference: Manual page 13
   */
  fan: {
    title: "Fan Mode",
    description: `Control when your system's fan operates:

• AUTO — Fan only runs when heating or cooling equipment is on
• ALWAYS ON — Fan runs continuously for better air circulation

Continuous operation improves air distribution but may increase energy use.`
  },

  /**
   * All Mode / Zone Mode
   * Reference: Manual pages 16, 21
   */
  allMode: {
    title: "Zone Mode",
    description: `Synchronize all zones to the same temperature settings:

• ALL ZONES — All zones use the same setpoints (zones 2-3 show dashes)
• INDIVIDUAL — Each zone can be controlled independently

When set to All Zones, temperature changes apply to every zone. Useful for vacation mode or whole-house comfort adjustments.`
  },

  /**
   * Hold Function
   * Reference: Manual pages 16, 21-22
   */
  hold: {
    title: "Hold Mode",
    description: `Override programmed schedule indefinitely:

• ON — Maintains current temperature setpoints until hold is released
• OFF — System follows programmed schedule

Use Hold when you need to maintain specific temperatures without changing your saved program. Examples: guests staying in a zone, extended vacation, or temporary comfort adjustments.

Press Hold again to return to your normal schedule.`
  },

  /**
   * Temperature Changes
   * Reference: Manual pages 9-10, 16
   */
  temperature: {
    title: "Temperature Settings",
    description: `Set desired heating and cooling temperatures for zones:

• Valid range: 45-80°F
• Temporary changes last until next scheduled period
• Use Hold to maintain settings indefinitely

Select the zone, mode (heat/cool), and target temperature. System will automatically reach the setpoint based on current conditions.`
  },

  /**
   * OUT Function (for future use if needed)
   * Reference: Manual pages 5, 16, 22
   */
  out: {
    title: "OUT / Unoccupied Mode",
    description: `Mark zones as unoccupied to save energy:

When a zone is set to OUT, it won't be conditioned unless temperature drops below 60°F or rises above 85°F.

This prevents unnecessary heating/cooling in unused areas while maintaining protection against extreme temperatures.`
  }
};
