#version 440

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float radius;
    float itemWidth;
    float itemHeight;
};

layout(binding = 1) uniform sampler2D source;

void main() {
    vec2 size = max(vec2(itemWidth, itemHeight), vec2(1.0));
    vec2 point = qt_TexCoord0 * size;
    float curve = min(radius, min(size.x, size.y) * 0.5);
    vec2 boxHalf = size * 0.5;
    vec2 delta = abs(point - boxHalf) - (boxHalf - vec2(curve));
    float dist = length(max(delta, vec2(0.0))) + min(max(delta.x, delta.y), 0.0) - curve;
    float cover = 1.0 - smoothstep(-0.75, 0.75, dist);
    fragColor = texture(source, qt_TexCoord0) * cover * qt_Opacity;
}
