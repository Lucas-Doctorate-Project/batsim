/*
 * Environmental Trace Reader Implementation
 * src/environmental_footprint_tracer_reader.cpp
 */

#include "environmental_footprint_tracer_reader.hpp"

#include <simgrid/s4u.hpp>
#include <simgrid/plugins/environmental_footprint.h>

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

EnvironmentalTraceReader::EnvironmentalTraceReader(const std::string& filename)
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

            simgrid::s4u::Actor::create(
                "env_zone_upd_" + host_name,
                hosts[0],
                [this, delay, hosts, property_to_update, new_values_str]() {
                    simgrid::s4u::this_actor::sleep_for(delay);
                    for (auto* h : hosts)
                        this->apply_update(h, property_to_update, new_values_str);
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
    auto data_map = parse_value_map(new_values_str);

    if (property_to_update == "energy_mix") {
        sg_host_set_energy_mix_composition(host, data_map);
    }
    else if (property_to_update == "carbon_intensity") {
        sg_host_set_carbon_intensities(host, data_map);
    }
    else if (property_to_update == "water_intensity") {
        sg_host_set_water_intensities(host, data_map);
    }
    else {
        std::cerr << "Warning: Unknown property in trace: " << property_to_update << std::endl;
    }
}

std::map<std::string, double> EnvironmentalTraceReader::parse_value_map(const std::string& input) 
{
    std::map<std::string, double> result;
    std::stringstream ss(input);
    std::string segment;

    while(std::getline(ss, segment, ';')) {
        auto pos = segment.find(':');
        if (pos != std::string::npos) {
            try {
                std::string key = segment.substr(0, pos);
                double val = std::stod(segment.substr(pos + 1));
                result[key] = val;
            } catch (...) {
                // Ignore malformed pairs safely
            }
        }
    }

    return result;
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