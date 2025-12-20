/*
 * Environmental Trace Reader Implementation
 * src/env_trace_reader.cpp
 */

#include "env_trace_reader.hpp"

#include <simgrid/s4u.hpp>
#include <simgrid/plugins/environmental_footprint.h>

#include <fstream>
#include <sstream>
#include <iostream>
#include <stdexcept>

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

            simgrid::s4u::Host* host = simgrid::s4u::Host::by_name_or_null(host_name);
            if (!host) 
                continue; 

            // Schedule the Event into the SimGrid engine
            simgrid::s4u::Timer::set(timestamp, [=]() {
                this->apply_update(host, property_to_update, new_values_str);
            });

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
    else if (property_to_update == "carbon_footprint") {
        sg_host_set_carbon_intensities(host, data_map);
    }
    else if (property_to_update == "water_footprint") {
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