#include "context.hpp"

/**
 * @brief Destroy a BatsimContext object
 */
BatsimContext::~BatsimContext()
{
    for (auto it : event_lists)
    {
        delete it.second;
    }
}

void BatsimContext::notify_environmental_change(double time, const std::string & zone_name, const std::string & property)
{
    if (!environmental_footprint_used)
        return;

    std::string event_type;
    if (property == "carbon_intensity")
        event_type = "ci";
    else if (property == "water_intensity")
        event_type = "wi";
    else if (property == "pue")
        event_type = "pue";
    else if (property == "wue")
        event_type = "wue";
    else
        return; // unknown property — ignore silently

    environmental_footprint_tracer.add_zone_event(time, zone_name, event_type);
}
