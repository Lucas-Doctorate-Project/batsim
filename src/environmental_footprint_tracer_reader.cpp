/*
 * Environmental Trace Reader Implementation
 * src/environmental_footprint_tracer_reader.cpp
 */

#include "environmental_footprint_tracer_reader.hpp"

#include <simgrid/s4u.hpp>
#include <simgrid/plugins/environmental_footprint.h>

#include "context.hpp"

#include <fstream>
#include <sstream>
#include <iostream>
#include <stdexcept>
#include <queue>

static simgrid::s4u::NetZone* find_zone_by_name(const std::string& name) {
    std::queue<simgrid::s4u::NetZone*> q;
    q.push(simgrid::s4u::Engine::get_instance()->get_netzone_root());
    while (!q.empty()) {
        auto* z = q.front(); q.pop();
        if (z->get_name() == name) return z;
        for (auto* child : z->get_children()) q.push(child);
    }
    return nullptr;
}

EnvironmentalTraceReader::EnvironmentalTraceReader(const std::string& filename, BatsimContext* context)
    : _context(context)
{
    read_trace(filename);
}

void EnvironmentalTraceReader::read_trace(const std::string& filename) 
{
    std::ifstream file(filename);
    if (!file.is_open()) {
        throw std::runtime_error("EnvironmentalTraceReader: Could not open file " + filename);
    }

    std::string line;
    std::getline(file, line); // Skip header

    while (std::getline(file, line)) {
        auto tokens = split_csv_line(line);
        if (tokens.size() < 4) continue;

        try {
            double timestamp = std::stod(tokens[0]);
            std::string host_name = tokens[1];
            std::string property_to_update = tokens[2];
            std::string new_values_str = tokens[3];

            simgrid::s4u::NetZone* zone = find_zone_by_name(host_name);
            xbt_assert(zone != nullptr,
                "env trace: '%s' is not a zone name", host_name.c_str());
            auto hosts = zone->get_all_hosts();

            double delay = timestamp - simgrid::s4u::Engine::get_clock();
            if (delay < 0) delay = 0;

            std::string zone_name = host_name;
            simgrid::s4u::Actor::create(
                "env_zone_upd_" + zone_name,
                hosts[0],
                [delay, hosts, property_to_update, new_values_str]() {
                    simgrid::s4u::this_actor::sleep_for(delay);
                    for (auto* h : hosts)
                        EnvironmentalTraceReader::apply_update(h, property_to_update, new_values_str);
                }
            );

        } catch (const std::exception& e) {
            std::cerr << "Error parsing environmental trace line: " << line 
                      << "\nReason: " << e.what() << std::endl;
        }
    }
    
    file.close();
}

void EnvironmentalTraceReader::apply_update(simgrid::s4u::Host* host, const std::string& property_to_update, const std::string& new_values_str) 
{
    try {
        double new_val = std::stod(new_values_str);

        if (property_to_update == "carbon_intensity") {
            sg_host_set_carbon_intensity(host, new_val);
        }
        else if (property_to_update == "water_intensity") {
            sg_host_set_water_intensity(host, new_val);
        }
        else if (property_to_update == "wue") {
            sg_host_set_wue(host, new_val);
        }
        else if (property_to_update == "pue") {
            sg_host_set_pue(host, new_val);
        }
        else {
            std::cerr << "Warning: Unknown property in trace: " << property_to_update << std::endl;
        }
    } catch (const std::exception& e) {
        std::cerr << "Error applying trace update: Invalid numeric value '" << new_values_str 
                  << "' for property '" << property_to_update << "'. Reason: " << e.what() << std::endl;
    }
}

std::vector<std::string> EnvironmentalTraceReader::split_csv_line(const std::string& line) {
    std::vector<std::string> tokens;
    std::string token;
    std::istringstream tokenStream(line);

    while (std::getline(tokenStream, token, ',')) {
        if (!token.empty() && token.front() == '"') token.erase(0, 1);
        if (!token.empty() && token.back() == '"') token.pop_back();
        tokens.push_back(token);
    }

    return tokens;
}