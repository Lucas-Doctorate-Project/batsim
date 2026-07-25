/*
 * Environmental Footprint Trace Reader for Batsim/SimGrid
 * src/environmental_footprint_tracer_reader.hpp
 */

#pragma once

#include <string>
#include <vector>
#include <map>

// Forward declarations to avoid heavy includes here
namespace simgrid {
    namespace s4u {
        class Host;
    }
}
struct BatsimContext;

class EnvironmentalTraceReader {
public:
    /**
     * @brief Constructor. Opens the file and schedules carbon intensity, water intensity, PUE, and WUE update events immediately. Fixed embodied inventory is configured through the platform and cannot be replaced through this trace API.
     * @param filename Path to the CSV trace file.
     * @param context  The Batsim context used to notify environmental changes.
     */
    explicit EnvironmentalTraceReader(const std::string& filename, BatsimContext* context);

private:
    BatsimContext* _context = nullptr; //!< Batsim context for notify_environmental_change calls
    /**
     * @brief Internal loop to parse the CSV and create SimGrid timers.
     */
    void read_trace(const std::string& filename);

    /**
     * @brief The callback executed when the simulation clock reaches the event time.
     */
    static void apply_update(simgrid::s4u::Host* host, const std::string& property_to_update, const std::string& new_values_str);


    /**
     * @brief Helper: CSV line splitter.
     */
    static std::vector<std::string> split_csv_line(const std::string& line);
};
