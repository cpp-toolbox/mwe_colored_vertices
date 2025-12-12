#include <array>
#include <iostream>

#include "graphics/colors/colors.hpp"
#include "graphics/draw_info/draw_info.hpp"
#include "graphics/shader_standard/shader_standard.hpp"
#include "graphics/vertex_geometry/vertex_geometry.hpp"

#include "system_logic/toolbox_engine/toolbox_engine.hpp"

#include "utility/glm_utils/glm_utils.hpp"
#include "utility/logger/logger.hpp"
#include "utility/model_loading/model_loading.hpp"

#define STB_IMAGE_IMPLEMENTATION
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include <stb_image.h>
#include <stb_image_write.h>

draw_info::IVPColor convert_ivpt_to_ivpc(const draw_info::IVPTextured &ivpt,
                                         bool solid_face_color = false // optional flag
) {
    assert(!ivpt.texture_path.empty() && "IVPTextured must have a texture to convert!");

    // load texture image
    int tex_width, tex_height, tex_channels;
    unsigned char *image_data = stbi_load(ivpt.texture_path.c_str(), &tex_width, &tex_height, &tex_channels, 3);
    if (!image_data) {
        throw std::runtime_error("Failed to load texture: " + ivpt.texture_path);
    }

    std::vector<glm::vec3> vertex_colors;
    vertex_colors.resize(ivpt.xyz_positions.size()); // preallocate

    if (solid_face_color) {
        // loop over triangles (indices in groups of 3)
        for (size_t i = 0; i + 2 < ivpt.indices.size(); i += 3) {
            int idx0 = ivpt.indices[i];
            int idx1 = ivpt.indices[i + 1];
            int idx2 = ivpt.indices[i + 2];

            glm::vec3 colors[3];
            int vertex_indices[3] = {idx0, idx1, idx2};

            // Sample the color at each vertex of the triangle
            for (int j = 0; j < 3; ++j) {
                glm::vec2 uv = ivpt.texture_coordinates[vertex_indices[j]];

                // Wrap UVs to [0,1)
                uv.x = uv.x - std::floor(uv.x);
                uv.y = uv.y - std::floor(uv.y);

                int px = static_cast<int>(uv.x * tex_width) % tex_width;
                int py = static_cast<int>(uv.y * tex_height) % tex_height;
                py = tex_height - 1 - py;

                int tex_idx = (py * tex_width + px) * 3;
                colors[j] = glm::vec3(image_data[tex_idx] / 255.0f, image_data[tex_idx + 1] / 255.0f,
                                      image_data[tex_idx + 2] / 255.0f);
            }

            // average the three vertex colors
            glm::vec3 avg_color = (colors[0] + colors[1] + colors[2]) / 3.0f;

            // Assign the same color to all three vertices
            vertex_colors[idx0] = avg_color;
            vertex_colors[idx1] = avg_color;
            vertex_colors[idx2] = avg_color;
        }
    } else {
        // per-vertex sampling
        for (size_t i = 0; i < ivpt.xyz_positions.size(); ++i) {
            glm::vec2 uv = ivpt.texture_coordinates[i];
            uv.x = uv.x - std::floor(uv.x);
            uv.y = uv.y - std::floor(uv.y);

            int px = static_cast<int>(uv.x * tex_width) % tex_width;
            int py = static_cast<int>(uv.y * tex_height) % tex_height;
            py = tex_height - 1 - py;

            int idx = (py * tex_width + px) * 3;
            vertex_colors[i] =
                glm::vec3(image_data[idx] / 255.0f, image_data[idx + 1] / 255.0f, image_data[idx + 2] / 255.0f);
        }
    }

    stbi_image_free(image_data);

    return draw_info::IVPColor(ivpt.indices, ivpt.xyz_positions, vertex_colors, ivpt.id, ivpt.name);
}

std::vector<draw_info::IVPColor> convert_ivpt_to_ivpc(const std::vector<draw_info::IVPTextured> &ivpts,
                                                      bool solid_face_color = false) {
    std::vector<draw_info::IVPColor> ivpcs;
    ivpcs.reserve(ivpts.size());
    for (const auto &ivpt : ivpts) {
        ivpcs.push_back(convert_ivpt_to_ivpc(ivpt, solid_face_color));
    }
    return ivpcs;
}

int main() {
    // TODO I shouldn't have to write down the requested shaders. how should it work?
    // it should be like the idea below for sounds...
    std::vector requested_shaders = {ShaderType::CWL_V_TRANSFORMATION_UBOS_1024_WITH_COLORED_VERTEX,
                                     ShaderType::ABSOLUTE_POSITION_WITH_COLORED_VERTEX};

    // TODO: sound types and the associated map should be generated from the sound direcotry so we don't have to do
    // anything manually. THen the sound system will automatically be constructed with the right data, something like
    // that for shaders as well
    std::unordered_map<SoundType, std::string> sound_type_to_file = {
        {SoundType::UI_HOVER, "assets/sounds/hover.wav"},
        {SoundType::UI_CLICK, "assets/sounds/click.wav"},
        {SoundType::UI_SUCCESS, "assets/sounds/success.wav"},
    };

    ToolboxEngine tbx_engine("mwe_vertex_colors", requested_shaders, sound_type_to_file);

    auto textured_model = model_loading::parse_model_into_ivpts("assets/models/spider_crossings/spider_crossings.obj");

    auto models = convert_ivpt_to_ivpc(textured_model, tbx_engine.configuration.is_on("graphics", "solid_face_color"));

    tbx_engine.shader_cache.set_uniform(ShaderType::CWL_V_TRANSFORMATION_UBOS_1024_WITH_COLORED_VERTEX,
                                        ShaderUniformVariable::CAMERA_TO_CLIP,
                                        tbx_engine.fps_camera.get_projection_matrix());

    tbx_engine.shader_cache.set_uniform(ShaderType::CWL_V_TRANSFORMATION_UBOS_1024_WITH_COLORED_VERTEX,
                                        ShaderUniformVariable::WORLD_TO_CAMERA,
                                        tbx_engine.fps_camera.get_view_matrix());

    if (tbx_engine.configuration.is_on("graphics", "backface_culling"))
        tbx_engine.window.enable_backface_culling();

    auto tick = [&](double dt) {
        tbx_engine.shader_cache.set_uniform(ShaderType::CWL_V_TRANSFORMATION_UBOS_1024_WITH_COLORED_VERTEX,
                                            ShaderUniformVariable::WORLD_TO_CAMERA,
                                            tbx_engine.fps_camera.get_view_matrix());

        tbx_engine.shader_cache.set_uniform(
            ShaderType::ABSOLUTE_POSITION_WITH_COLORED_VERTEX, ShaderUniformVariable::ASPECT_RATIO,
            glm_utils::tuple_to_vec2(tbx_engine.window.get_aspect_ratio_in_simplest_terms()));

        tbx_engine.update_active_mouse_mode(tbx_engine.igs_menu_active);
        tbx_engine.update_camera_position_with_default_movement(dt);

        for (auto &model : models) {
            tbx_engine.batcher.cwl_v_transformation_ubos_1024_with_colored_vertex_shader_batcher.queue_draw(model);
        }

        tbx_engine.process_and_queue_render_input_graphics_sound_menu();
        tbx_engine.draw_chosen_engine_stats();

        tbx_engine.batcher.absolute_position_with_colored_vertex_shader_batcher.draw_everything();
        tbx_engine.batcher.cwl_v_transformation_ubos_1024_with_colored_vertex_shader_batcher.draw_everything();

        tbx_engine.sound_system.play_all_sounds();
        global_logger->info(tbx_engine.input_state.get_visual_keyboard_state());

        global_logger->info("{}", dt);
    };
    // todo make atemplted function that wraps a constnt type value
    auto term = [&]() { return tbx_engine.window_should_close(); };
    tbx_engine.start(tick, term);
}
