"""Simplified Chinese display text for the desktop GUI.

Only what the user reads is translated. Combo box values, section titles used
for icon lookup, and persisted state keep their English identifiers, so saved
GUI states and the runtime parameters are unaffected. Text without an entry
here falls back to English.
"""

from __future__ import annotations

import html
import re

from qtpy import QtCore, QtWidgets

_enabled = False
_qt_translators: list[QtCore.QTranslator] = []

# Keys are the lower-cased text shown on labels, buttons, section titles and tabs.
_UI_TEXT = {
    # tabs
    'main': '主要',
    'film': '胶片',
    'print': '相纸',
    'advanced': '高级',
    'config': '配置',
    # section titles
    'import rgb': '导入 RGB 图像',
    'import raw': 'RAW 设置',
    'input': '输入',
    'camera': '相机',
    'profiles': '胶片与相纸',
    'exposure control': '曝光控制',
    'enlarger': '放大机',
    'scanner': '扫描仪',
    'crop and upscale': '裁切与放大',
    'output': '输出',
    'grain': '颗粒',
    'halation': '光晕',
    'couplers': '成色剂',
    'chemistry': '化学冲洗',
    'glare': '眩光',
    'preflash': '预闪',
    'diffusion': '柔光滤镜',
    'spectral upsampling': '光谱上采样',
    'input gamut compress': '输入色域压缩',
    'output gamut compress': '输出色域压缩',
    'tune': '微调',
    'experimental': '实验功能',
    'gui parameters': '界面参数',
    'display': '显示',
    'napari layers': 'napari 图层',
    # buttons and placeholders
    'preview': '预览',
    'scan': '扫描',
    'save': '保存',
    'select file': '选择文件',
    'reprocess raw': '重新处理 RAW',
    'save current as default': '将当前设置设为默认',
    'save current to file': '将当前设置存为文件',
    'load from file': '从文件加载',
    'restore factory default': '恢复出厂默认',
    'update': '更新',
    'ccw rotate': '逆时针旋转',
    'cw rotate': '顺时针旋转',
    'reset view': '重置视图',
    'no raw selected': '未选择 RAW 文件',
    'no image selected': '未选择图像',
    'ready': '就绪',
    # shared field labels
    'active': '启用',
    'amount': '强度',
    'blur': '模糊',
    'exposure': '曝光',
    'y filter shift': 'Y 滤镜偏移',
    'm filter shift': 'M 滤镜偏移',
    'lens blur': '镜头模糊',
    'algorithm': '算法',
    'knee': '拐点',
    # couplers
    'inhibition samelayer': '同层抑制',
    'inhibition interlayer': '层间抑制',
    'gamma samelayer rgb': '同层 Gamma (RGB)',
    'gamma interlayer r to gb': '层间 Gamma R→GB',
    'gamma interlayer g to rb': '层间 Gamma G→RB',
    'gamma interlayer b to rg': '层间 Gamma B→RG',
    'diffusion size um': '扩散尺寸 (µm)',
    # halation
    'scatter amount': '散射强度',
    'scatter spatial scale': '散射范围倍率',
    'halation amount': '光晕强度',
    'halation spatial scale': '光晕范围倍率',
    'boost ev': '高光增强 (EV)',
    'protect ev': '保护范围 (EV)',
    'boost range': '增强过渡',
    'scatter core um': '散射核心 (µm)',
    'scatter tail um': '散射拖尾 (µm)',
    'scatter tail weight': '散射拖尾权重',
    'halation strength': '光晕幅度',
    'halation first sigma um': '首次反射 Sigma (µm)',
    'halation n bounces': '光晕反射次数',
    'halation bounce decay': '光晕反射衰减',
    'halation renormalize': '光晕重新归一化',
    # grain
    'sublayers active': '启用子层',
    'particle area um2': '颗粒面积 (µm²)',
    'particle scale': '颗粒缩放',
    'particle scale layers': '子层颗粒缩放',
    'density min': '最小密度',
    'uniformity': '均匀度',
    'blur dye clouds um': '染料云模糊 (µm)',
    'micro structure': '微观结构',
    # glare
    'percent': '比例',
    'roughness': '粗糙度',
    # chemistry
    'gamma factor': 'Gamma 系数',
    'gamma factor fast': 'Gamma 系数（快层）',
    'gamma factor slow': 'Gamma 系数（慢层）',
    'gamma factor red': 'Gamma 系数（红）',
    'gamma factor green': 'Gamma 系数（绿）',
    'gamma factor blue': 'Gamma 系数（蓝）',
    'developer exhaustion': '显影液衰竭',
    # diffusion
    'filter family': '滤镜类型',
    'strength': '强度档位',
    'spatial scale': '范围倍率',
    'halo warmth': '光晕色温',
    'core intensity': '核心强度',
    'core size': '核心尺寸',
    'halo intensity': '光晕强度',
    'halo size': '光晕尺寸',
    'bloom intensity': '泛光强度',
    'bloom size': '泛光尺寸',
    # camera
    'film format mm': '胶片画幅 (mm)',
    'lens blur um': '镜头模糊 (µm)',
    'auto exposure method': '测光方式',
    'auto exposure': '自动曝光',
    'exposure compensation ev': '曝光补偿 (EV)',
    # scanner
    'white correction': '白点校正',
    'white level': '白电平',
    'black correction': '黑点校正',
    'black level': '黑电平',
    'unsharp mask': 'USM 锐化',
    # input
    'input color space': '输入色彩空间',
    'apply cctf decoding': '应用 CCTF 解码',
    'upscale factor': '放大倍数',
    'crop': '裁切',
    'crop center': '裁切中心',
    'crop size': '裁切尺寸',
    'hanatos2025 adaptation window': 'hanatos2025 适配窗口',
    'hanatos2025 adaptation surface': 'hanatos2025 适配曲面',
    'spectral gaussian blur': '光谱高斯模糊',
    # special
    'film channel swap': '胶片通道交换',
    'print channel swap': '相纸通道交换',
    'film gamma factor': '胶片 Gamma 系数',
    # display
    'use display transform': '使用显示器色彩转换',
    'gray 18% canvas': '18% 灰背景',
    'white padding': '白边宽度',
    'preview max size': '预览最大尺寸',
    'output interpolation': '输出插值',
    # simulation
    'film profile': '胶片型号',
    'print profile': '相纸型号',
    'print illuminant': '印放光源',
    'print auto compensation': '印放自动补偿',
    'print exposure': '印放曝光',
    'print y filter shift': '印放 Y 滤镜偏移',
    'print m filter shift': '印放 M 滤镜偏移',
    'output color space': '输出色彩空间',
    'saving color space': '保存色彩空间',
    'saving cctf encoding': '保存时应用 CCTF 编码',
    'auto preview': '自动预览',
    'scan film': '扫描负片',
    'scan for print': '按印刷扫描',
    # raw import
    'white balance': '白平衡',
    'temperature': '色温',
    'tint': '色调',
    'lens correction': '镜头校正',
}

_TOOLTIPS = {
    # couplers
    'Enable DIR coupler inhibition.': '启用 DIR 成色剂抑制。',
    'Global multiplier on the DIR coupler inhibition matrix. 1.0 leaves the per-channel gammas as-is.': 'DIR 成色剂抑制矩阵的整体倍率。1.0 表示保持各通道 Gamma 不变。',
    'Multiplier on the same-layer (diagonal) inhibition. Controls overall contrast / gamma reduction within each RGB layer.': '同层（对角线）抑制的倍率。控制每个 RGB 层内部的整体对比度 / Gamma 降低量。',
    'Multiplier on the cross-layer (off-diagonal) inhibition. Controls saturation enhancement from interlayer DIR effects.': '跨层（非对角线）抑制的倍率。控制层间 DIR 效应带来的饱和度增强。',
    "Per-channel same-layer DIR gamma (R, G, B). Effective gamma reduction of each layer's density curve.": '各通道的同层 DIR Gamma (R, G, B)，即每层密度曲线实际降低的 Gamma。',
    'DIR inhibition from the R layer onto the G and B layers respectively (g_R->G, g_R->B).': 'R 层分别对 G、B 层的 DIR 抑制 (g_R->G, g_R->B)。',
    'DIR inhibition from the G layer onto the R and B layers respectively (g_G->R, g_G->B).': 'G 层分别对 R、B 层的 DIR 抑制 (g_G->R, g_G->B)。',
    'DIR inhibition from the B layer onto the R and G layers respectively (g_B->R, g_B->G).': 'B 层分别对 R、G 层的 DIR 抑制 (g_B->R, g_B->G)。',
    'Sigma in um for the diffusion of the couplers, (5-20 um), controls sharpness and affects saturation.': '成色剂扩散的 Sigma，单位 µm（5-20 µm），控制锐度并影响饱和度。',
    # halation
    'Enable halation and in-emulsion scatter.': '启用光晕和乳剂内散射。',
    'High-level scatter strength. 1.0 = full physical scatter, 0.0 = no scatter. Scales the fraction of light that undergoes in-emulsion scattering.': '散射总强度。1.0 为完整物理散射，0.0 为无散射。缩放在乳剂内发生散射的光线比例。',
    'High-level scatter size multiplier (1.0 = physical defaults). Scales both core and tail sigmas.': '散射范围总倍率（1.0 为物理默认值），同时缩放核心和拖尾的 Sigma。',
    'High-level halation strength multiplier (1.0 = physical defaults). Scales the per-channel halation amplitudes.': '光晕强度总倍率（1.0 为物理默认值），缩放各通道的光晕幅度。',
    'High-level halation size multiplier (1.0 = physical defaults). Scales the first-bounce sigma.': '光晕范围总倍率（1.0 为物理默认值），缩放首次反射的 Sigma。',
    'Maximum highlight boost in stops.': '高光增强的最大值，单位为挡。',
    'Protected range above midgray for the boost onset in stops.': '中灰以上不参与增强的保护范围，单位为挡。',
    'Controls how quickly the highlight boost ramps in, from 0 to 1.': '控制高光增强渐入的快慢，范围 0 到 1。',
    'Sigma of the scatter core Gaussian per channel [R,G,B], in micrometers. Controls fine-scale sharpness loss in the emulsion.': '各通道 [R,G,B] 散射核心高斯的 Sigma，单位 µm。控制乳剂内细节锐度的损失。',
    'Decay constant of the scatter exponential tail per channel [R,G,B], in micrometers (internally approximated by a sum of Gaussians). Controls extended low-level spread within the emulsion.': '各通道 [R,G,B] 散射指数拖尾的衰减常数，单位 µm（内部用多个高斯之和近似）。控制乳剂内大范围的低强度扩散。',
    'Weight of the scatter tail Gaussian per channel [R,G,B] (0-1). Tail weight + core weight = 1. Higher values put more scattered light into the long tail.': '各通道 [R,G,B] 散射拖尾高斯的权重（0-1）。拖尾权重 + 核心权重 = 1。数值越高，进入长拖尾的散射光越多。',
    'Total back-reflection halation amplitude per channel [R,G,B] (0-1). Typical red channel: weak AH 0.02-0.08, no AH 0.08-0.25. The blue channel is usually near zero.': '各通道 [R,G,B] 背面反射光晕的总幅度（0-1）。红通道典型值：弱防光晕层 0.02-0.08，无防光晕层 0.08-0.25。蓝通道通常接近 0。',
    'Sigma of the first halation bounce per channel [R,G,B], in micrometers. Set by the base thickness (40-80 um for typical cine/still bases).': '各通道 [R,G,B] 首次光晕反射的 Sigma，单位 µm。由片基厚度决定（常见电影/照相片基为 40-80 µm）。',
    'Number of multi-bounce Gaussians summed in the halation pass. Subsequent bounces use sqrt(k)-spaced widths. Typical: 2-3.': '光晕计算中叠加的多次反射高斯数量。后续反射宽度按 sqrt(k) 递增。典型值 2-3。',
    'Per-bounce amplitude decay ratio (rho). Physical range 0.3-0.7. Controls how fast the halation energy falls off between bounces.': '每次反射的幅度衰减比 (rho)，物理范围 0.3-0.7。控制光晕能量在多次反射间衰减的快慢。',
    'If enabled, divide by (1 + sum of bounce amplitudes) so mid-grey is preserved. If disabled, halation is purely additive and subtly lifts shadows as well as highlights.': '启用时除以（1 + 各次反射幅度之和）以保持中灰。关闭时光晕为纯叠加，会轻微提亮暗部和高光。',
    # grain
    'Add grain to the negative': '为负片添加颗粒',
    'Enable per-sublayer grain structure.': '启用按子层计算的颗粒结构。',
    'Area of the particles in um2, relates to ISO. Approximately 0.1 for ISO 100, 0.1 for ISO 200, 0.4 for ISO 400 and so on.': '颗粒面积，单位 µm²，与 ISO 相关。大约 ISO 100 为 0.1，ISO 200 为 0.1，ISO 400 为 0.4，依此类推。',
    'Scale of particle area for the RGB layers, multiplies particle_area_um2': 'RGB 各层的颗粒面积缩放，与“颗粒面积”相乘',
    'Scale of particle area for the sublayers in every color layer, multiplies particle_area_um2': '每个颜色层中各子层的颗粒面积缩放，与“颗粒面积”相乘',
    'Minimum density of the grain, typical values (0.03-0.06)': '颗粒的最小密度，典型值 0.03-0.06',
    'Uniformity of the grain, typical values (0.94-0.98)': '颗粒的均匀度，典型值 0.94-0.98',
    'Sigma of gaussian blur in pixels for the grain, to be increased at high magnifications, (should be 0.8-0.9 at high resolution, reduce down to 0.6 for lower res).': '颗粒高斯模糊的 Sigma，单位像素，高倍放大时应增大（高分辨率建议 0.8-0.9，低分辨率可降到 0.6）。',
    'Scale the sigma of gaussian blur in um for the dye clouds, to be used at high magnifications, (default 1)': '染料云高斯模糊的 Sigma 缩放，单位 µm，用于高倍放大（默认 1）',
    'Parameter for micro-structure due to clumps at the molecular level, [sigma blur of micro-structure / ultimate light-resolution (0.10 um default), size of molecular clumps in nm (30 nm default)]. Only for insane magnifications.': '分子级团簇形成的微观结构参数：[微观结构模糊 Sigma / 极限光学分辨率（默认 0.10 µm），分子团簇尺寸（默认 30 nm）]。仅用于极高倍放大。',
    # glare
    'Add glare to the print': '为相纸添加眩光',
    'Percentage of the glare light (typically 0.1-0.25)': '眩光的光量比例（通常为 0.1-0.25）',
    'Roughness of the glare light (0-1)': '眩光的粗糙度（0-1）',
    'Sigma of gaussian blur in pixels for the glare': '眩光高斯模糊的 Sigma，单位像素',
    # chemistry
    'Enable print density-curve morphing.': '启用相纸密度曲线变形。',
    'Global coupled gamma multiplier for the print density curves.': '相纸密度曲线的整体 Gamma 倍率。',
    'Gamma factor applied to the fast sub-layer.': '应用于快速子层的 Gamma 系数。',
    'Gamma factor applied to the mid and slow sub-layers.': '应用于中速和慢速子层的 Gamma 系数。',
    'Per-channel gamma factor applied to the red channel.': '应用于红通道的 Gamma 系数。',
    'Per-channel gamma factor applied to the green channel.': '应用于绿通道的 Gamma 系数。',
    'Per-channel gamma factor applied to the blue channel.': '应用于蓝通道的 Gamma 系数。',
    'Blend all three print sub-layers toward the matched Gumbel shoulder while preserving midgray via a common horizontal offset.': '将三个相纸子层向匹配的 Gumbel 肩部混合，并通过统一的水平偏移保持中灰。',
    # preflash
    'Preflash exposure value in ev for the print': '相纸预闪曝光量，单位 EV',
    'Shift the Y filter of the enlarger from the neutral position for the preflash, typical values (-20-20), in Kodak CC units': '预闪时放大机 Y 滤镜相对中性位置的偏移，典型值 -20 到 20，单位为柯达 CC',
    'Shift the M filter of the enlarger from the neutral position for the preflash, typical values (-20-20), in Kodak CC units': '预闪时放大机 M 滤镜相对中性位置的偏移，典型值 -20 到 20，单位为柯达 CC',
    # diffusion
    'Toggle the diffusion filter (Pro-Mist family).': '开关柔光滤镜（Pro-Mist 系列）。',
    'PSF family. pro_mist / glimmerglass / cinebloom are transparent (energy-preserving); black_pro_mist absorbs a fraction of the deflected light, lifting shadows by reducing local contrast.': 'PSF 类型。pro_mist / glimmerglass / cinebloom 为透明型（能量守恒）；black_pro_mist 会吸收部分偏折光，通过降低局部对比度提亮暗部。',
    'Commercial filter stop: 0, 1/8=0.125, 1/4=0.25, 1/2=0.5, 1, 2. Maps internally to the (p_s, p_a) deflected/absorbed photon fractions.': '市售滤镜档位：0、1/8=0.125、1/4=0.25、1/2=0.5、1、2。内部映射为偏折/吸收光子比例 (p_s, p_a)。',
    'Multiplier on the image-plane PSF widths (all per-group lambdas). Adjust for image-format / print-size differences.': '像面 PSF 宽度（各组 lambda）的倍率。用于适配不同画幅 / 印放尺寸。',
    "Additive offset on the family's halo warmth axis. Positive = warm outer halo / cool inner halo. Energy-preserving per channel. 0 = use family default.": '在该滤镜类型的光晕色温轴上叠加偏移。正值为外圈偏暖、内圈偏冷。各通道能量守恒。0 表示使用默认值。',
    'Advanced. Multiplier on the core weight; the three group weights are renormalized to sum to 1. 1.0 = use family default.': '高级选项。核心权重的倍率；三组权重会重新归一化为总和 1。1.0 表示使用默认值。',
    'Advanced. Multiplier on the core lambda. 1.0 = use family default.': '高级选项。核心 lambda 的倍率。1.0 表示使用默认值。',
    'Advanced. Multiplier on the halo weight; the three group weights are renormalized to sum to 1. 1.0 = use family default.': '高级选项。光晕权重的倍率；三组权重会重新归一化为总和 1。1.0 表示使用默认值。',
    'Advanced. Multiplier on the halo lambda. 1.0 = use family default.': '高级选项。光晕 lambda 的倍率。1.0 表示使用默认值。',
    'Advanced. Multiplier on the bloom weight; the three group weights are renormalized to sum to 1. 1.0 = use family default.': '高级选项。泛光权重的倍率；三组权重会重新归一化为总和 1。1.0 表示使用默认值。',
    'Advanced. Multiplier on the bloom lambda. 1.0 = use family default.': '高级选项。泛光 lambda 的倍率。1.0 表示使用默认值。',
    # camera
    'Long edge of the film format in millimeters, e.g. 8, 16, 35, 60, 120.': '胶片画幅的长边，单位毫米，例如 8、16、35、60、120。',
    'Sigma of gaussian filter in um for the camera lens blur. About 5 um for typical lenses, down to 2-4 um for high quality lenses; used for sharp input simulations without lens blur.': '相机镜头模糊的高斯 Sigma，单位 µm。普通镜头约 5 µm，高品质镜头可低至 2-4 µm；用于模拟没有镜头模糊的锐利输入。',
    "Metering method used by the virtual camera's auto-exposure.": '虚拟相机自动曝光使用的测光方式。',
    'Use the auto-exposure feature of the virtual camera.': '使用虚拟相机的自动曝光功能。',
    'Add a bias to the auto-exposure of the camera.': '为相机的自动曝光增加偏移量。',
    # scanner
    'Sigma of gaussian filter in pixel for the scanner lens blur.': '扫描仪镜头模糊的高斯 Sigma，单位像素。',
    'Enable white point correction applied to the scanner output.': '对扫描输出启用白点校正。',
    'Target white level applied when white correction is enabled.': '启用白点校正时使用的目标白电平。',
    'Enable black point correction applied to the scanner output.': '对扫描输出启用黑点校正。',
    'Target black level applied when black correction is enabled.': '启用黑点校正时使用的目标黑电平。',
    'Apply unsharp mask to the scan, [sigma in pixel, amount].': '对扫描结果应用 USM 锐化，[Sigma（像素）, 强度]。',
    # gamut compression
    'Compress input chromaticities toward the visible spectral locus before spectral upsampling. Off passes input through unchanged.': '在光谱上采样前，把输入色度压缩到可见光谱轨迹内。关闭时输入保持不变。',
    'xy: radial compression in CIE 1931 chromaticity (ACES RGC family, hue-preserving). oklch: perceptual chroma reduction at constant Oklch (L, h).': 'xy：在 CIE 1931 色度图上径向压缩（ACES RGC 系列，保持色相）。oklch：在 Oklch 中保持 L、h 不变并降低感知彩度。',
    'Reinhard knee (threshold, limit, power). Defaults (0.0, 1.0, 6.0) apply a soft full-range roll-off that asymptotes at the spectral locus boundary.': 'Reinhard 拐点（阈值、极限、幂）。默认值 (0.0, 1.0, 6.0) 会在全范围柔和滚降，并渐近于光谱轨迹边界。',
    'off: disable output gamut compression. cam16ucs (default): CAM16-UCS chroma reduction with the smoothest constant-hue behavior. oklch: perceptual chroma reduction in OkLab, preserves hue + lightness. aces_rgc: per-channel ACES RGC v1.3, matches Resolve/Nuke/OCIO. oklrab/jzazbz: alternative perceptual spaces.': 'off：关闭输出色域压缩。cam16ucs（默认）：CAM16-UCS 彩度压缩，色相最平滑稳定。oklch：在 OkLab 中降低感知彩度，保持色相和明度。aces_rgc：按通道的 ACES RGC v1.3，与 Resolve/Nuke/OCIO 一致。oklrab/jzazbz：其他感知色彩空间。',
    'Reinhard knee (threshold, limit, power) on normalized chroma C/C_max. Default (0.0, 1.0, 6.0) rolls off smoothly from the center with the asymptote on the output cube edge.': '作用于归一化彩度 C/C_max 的 Reinhard 拐点（阈值、极限、幂）。默认值 (0.0, 1.0, 6.0) 从中心平滑滚降，并渐近于输出色彩立方体边缘。',
    # input
    'Color space of the input image, will be internally converted to sRGB and negative values clipped': '输入图像的色彩空间，内部会转换为 sRGB 并裁掉负值',
    'Apply the inverse cctf transfer function of the color space': '应用该色彩空间的 CCTF 反向传递函数',
    'Scale image size up to increase resolution': '放大图像尺寸以提高分辨率',
    'Crop image to a fraction of the original size to preview details at full scale': '将图像裁切为原尺寸的一部分，以便按全尺寸预览细节',
    'Center of the crop region in relative coordinates in x, y (0-1)': '裁切区域中心的相对坐标 x, y（0-1）',
    'Normalized size of the crop region in x, y (0,1), as fraction of the long side.': '裁切区域的归一化尺寸 x, y（0-1），以长边的比例表示。',
    'Method to upsample the spectral resolution of the image, hanatos2025 works on the full visible locus, mallett2019 works only on sRGB (will clip input).': '图像光谱上采样的方法。hanatos2025 适用于整个可见光谱轨迹，mallett2019 仅适用于 sRGB（会裁切输入）。',
    'Apply the hanatos2025 bandpass adaptation window when reconstructing spectra.': '重建光谱时应用 hanatos2025 带通适配窗口。',
    'Apply the hanatos2025 surface adaptation polynomial when reconstructing spectra.': '重建光谱时应用 hanatos2025 曲面适配多项式。',
    'Sigma in nm for Gaussian blur applied to reconstructed spectra.': '应用于重建光谱的高斯模糊 Sigma，单位 nm。',
    # special
    'Gamma factor of the density curves of the negative, < 1 reduce contrast, > 1 increase contrast': '负片密度曲线的 Gamma 系数，小于 1 降低对比度，大于 1 提高对比度',
    # display
    'Use Pillow.ImageCms to retrive the display transform (only in Windows) and apply it to the napari viewer output, if disabled the output color space is used': '使用 Pillow.ImageCms 获取显示器色彩转换（仅限 Windows）并应用到 napari 视图；关闭时使用输出色彩空间',
    'Use neutral 18% gray as backgroung to judge the exposure and neutral colors': '使用中性 18% 灰作为背景，便于判断曝光和中性色',
    'Expand the white border layer around the normalized preview frame, expressed as a fraction of the image long edge.': '扩大预览画面周围的白边，数值为图像长边的比例。',
    'max size of the long edge of the preview image in pixels': '预览图长边的最大尺寸，单位像素',
    'Napari interpolation mode used to display the output layer in the viewer.': '在视图中显示输出图层时使用的 napari 插值方式。',
    # simulation
    'Film stock to simulate': '要模拟的胶片',
    'Print paper to simulate': '要模拟的相纸',
    'Print illuminant to simulate': '要模拟的印放光源',
    'Auto adjust the print exposure for the camera exposure compensation ev': '根据相机曝光补偿自动调整印放曝光',
    'Changes the exposure time set in the virtual enlarger': '修改虚拟放大机的曝光时间',
    'Y filter shift of the color enlarger from a neutral position, in Kodak CC units': '彩色放大机 Y 滤镜相对中性位置的偏移，单位为柯达 CC',
    'M filter shift of the color enlarger from a neutral position, in Kodak CC units': '彩色放大机 M 滤镜相对中性位置的偏移，单位为柯达 CC',
    'Output color space of the simulation': '模拟结果的输出色彩空间',
    'Color space of the saved image file': '保存图像文件使用的色彩空间',
    'Add or not the CCTF to the saved image file': '保存图像文件时是否添加 CCTF',
    'trigger the preview after every change of gui parameters, use mouse scrollwheel on parameters field, read preview tooltip for details': '每次修改界面参数后自动触发预览，可在参数框上用鼠标滚轮调整，详情见“预览”按钮的提示',
    'Show a scan of the negative instead of the print': '显示负片的扫描结果，而不是相纸成品',
    'Scan the image for print, ie white and black correction of the scanner are active, and glare is deactivated.': '按印刷用途扫描，即启用扫描仪的白点和黑点校正，并关闭眩光。',
    'run the simulation on a small preview and deactivates grain, halation, blurs, unsharp mask (diffusion filters are active)': '在小尺寸预览图上运行模拟，并关闭颗粒、光晕、模糊和 USM 锐化（柔光滤镜仍然生效）',
    'Run the full simulation on the full-resolution input': '对全分辨率输入运行完整模拟',
    'Save the current output layer to an image file': '将当前输出图层保存为图像文件',
    # raw import
    'Select white balance settings, if custom you can tune temperature and tint': '选择白平衡设置，选择“自定义”时可调整色温和色调',
    'Temperature in Kelvin for the custom whitebalance, not used for the other white balance settings': '自定义白平衡的色温，单位开尔文，其他白平衡设置不使用',
    'Tint value for the custom white balance, not used for the other white balance settings': '自定义白平衡的色调值，其他白平衡设置不使用',
    'Apply lens corrections': '应用镜头校正',
    'Load and process a raw file using rawpy, output colorspace and cctf as defined in current input widget state': '使用 rawpy 加载并处理 RAW 文件，输出色彩空间和 CCTF 取自当前“输入”面板的设置',
    # viewer
    'Pixel of the screen mapped 1 to 1 to the image pixel': '屏幕像素与图像像素 1:1 对应',
    '2 screen pixels mapped to 1 image pixel': '2 个屏幕像素对应 1 个图像像素',
    '4 screen pixels mapped to 1 image pixel': '4 个屏幕像素对应 1 个图像像素',
}

_MESSAGES = {
    'Saved current GUI state as the startup default': '已将当前界面设置保存为启动默认值',
    'Restored factory default GUI state': '已恢复出厂默认设置',
    'Save GUI state': '保存界面设置',
    'Load GUI state': '加载界面设置',
    'Save output': '保存输出',
    'Save output image': '保存输出图像',
    'Load raw': '加载 RAW',
    'Run simulation': '运行模拟',
    'Select input raw': '选择输入 RAW 文件',
    'select input raw': '选择输入 RAW 文件',
    'Select input image': '选择输入图像',
    'select input image': '选择输入图像',
    'Save current as default': '将当前设置设为默认',
    'Restore factory default': '恢复出厂默认',
    'Failed to save default GUI state.': '保存默认界面设置失败。',
    'Failed to save GUI state.': '保存界面设置失败。',
    'Failed to load GUI state.': '加载界面设置失败。',
    'Failed to clear the saved startup default.': '清除已保存的启动默认值失败。',
    'Failed to load RAW image.': '加载 RAW 图像失败。',
    'Failed to save output image.': '保存输出图像失败。',
    'Simulation failed.': '模拟失败。',
    'Run a simulation before saving the output layer.': '请先运行模拟，再保存输出图层。',
    'Load an input image before running the simulation.': '请先加载输入图像，再运行模拟。',
    'Loading raw...': '正在加载 RAW……',
    'Load raw failed': '加载 RAW 失败',
    'Loaded raw': 'RAW 已加载',
    'Loaded raw, lens correction not applied': 'RAW 已加载，未应用镜头校正',
    'Simulation already running': '模拟正在运行',
    'Display transform: disabled': '显示器色彩转换：已关闭',
    'Display transform: no display profile, using raw preview': '显示器色彩转换：未找到显示器配置文件，使用原始预览',
    'Display transform: transform failed, using raw preview': '显示器色彩转换：转换失败，使用原始预览',
    'Display transform unavailable: no display profile detected, disabled': '显示器色彩转换不可用：未检测到显示器配置文件，已关闭',
}

_MODE_LABELS = {'preview': '预览', 'scan': '扫描', 'simulation': '模拟'}

_MESSAGE_PATTERNS = (
    (re.compile(r'^Computing (preview|scan)\.\.\.$'), lambda m: f'正在计算{_MODE_LABELS[m[1]]}……'),
    (re.compile(r'^(Preview|Scan) completed\. (.*)$', re.S), lambda m: f'{_MODE_LABELS[m[1].lower()]}完成。{translate(m[2])}'),
    (re.compile(r'^(Preview|Scan|Simulation) failed$'), lambda m: f'{_MODE_LABELS[m[1].lower()]}失败'),
    (re.compile(r'^Display transform: display profile found \((.*)\)$'), lambda m: f'显示器色彩转换：已找到显示器配置文件（{m[1]}）'),
    (re.compile(r'^Display transform: active \((.*)\)$'), lambda m: f'显示器色彩转换：已启用（{m[1]}）'),
    (re.compile(r'^Saved GUI state to (.*)$'), lambda m: f'界面设置已保存到 {m[1]}'),
    (re.compile(r'^Loaded GUI state from (.*)$'), lambda m: f'已从 {m[1]} 加载界面设置'),
    (re.compile(r'^Saved output image to (.*), but failed to copy metadata: (.*)$', re.S), lambda m: f'输出图像已保存到 {m[1]}，但复制元数据失败：{m[2]}'),
    (re.compile(r'^Saved output image to (.*)$'), lambda m: f'输出图像已保存到 {m[1]}'),
    (re.compile(r'^Loaded raw and applied lens correction: (.*)$', re.S), lambda m: f'RAW 已加载并应用镜头校正：{m[1]}'),
)

# Values stay in English in the combo box model; only their display changes.
_ENUM_TEXT = {
    'as_shot': '机内设置',
    'daylight': '日光',
    'tungsten': '钨丝灯',
    'custom': '自定义',
    'center_weighted': '中央重点',
    'matrix': '矩阵',
    'multi_zone': '多区',
    'partial': '局部',
    'highlight_weighted': '高光优先',
    'median': '中位数',
    'average': '平均',
    'nearest': '最近邻',
    'linear': '线性',
    'cubic': '三次',
    'off': '关闭',
    'cine': '电影',
    'still': '照相',
}


def translate(text: str) -> str:
    """Return the Chinese text for ``text``, or ``text`` itself when disabled or unknown."""
    if not _enabled or not text:
        return text
    exact = _TOOLTIPS.get(text) or _MESSAGES.get(text)
    if exact is not None:
        return exact
    ui_text = _UI_TEXT.get(text.strip().lower())
    if ui_text is not None:
        return ui_text
    head, separator, detail = text.partition('\n\n')
    if separator and head in _MESSAGES:
        return f'{_MESSAGES[head]}{separator}{detail}'
    for pattern, render in _MESSAGE_PATTERNS:
        match = pattern.match(text)
        if match is not None:
            return render(match)
    return text


def translate_enum(value: str) -> str:
    if not _enabled:
        return value
    return _ENUM_TEXT.get(value, value)


class LocalizedMessageBox:
    """Drop-in for the ``QMessageBox`` static calls used by the controllers."""

    @staticmethod
    def critical(parent, title: str, text: str):
        return QtWidgets.QMessageBox.critical(parent, translate(title), translate(text))

    @staticmethod
    def warning(parent, title: str, text: str):
        return QtWidgets.QMessageBox.warning(parent, translate(title), translate(text))


def _install_qt_translations() -> None:
    """Load Qt's own Chinese strings (dialog buttons, spin box and line edit menus)."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    translations_path = QtCore.QLibraryInfo.path(QtCore.QLibraryInfo.LibraryPath.TranslationsPath)
    translator = QtCore.QTranslator(app)
    if translator.load('qtbase_zh_CN', translations_path):
        app.installTranslator(translator)
        _qt_translators.append(translator)


def _translate_widget(widget: QtWidgets.QWidget) -> None:
    tooltip = widget.toolTip()
    translated_tooltip = translate(tooltip)
    if translated_tooltip != tooltip:
        # Rich text lets Qt wrap long tooltips instead of drawing one very wide line.
        widget.setToolTip(f'<qt>{html.escape(translated_tooltip)}</qt>')
    if widget.objectName() == 'valueSlider':
        hint = widget.toolTip()
        widget.setToolTip(f'{hint[:-5]}<br>双击滑块恢复初始值</qt>' if hint.endswith('</qt>') else '双击滑块恢复初始值')
    if isinstance(widget, QtWidgets.QAbstractSpinBox):
        # Windows regions with native digits (e.g. zh-Hans-HK) make Qt draw garbled numbers.
        widget.setLocale(QtCore.QLocale.c())
    elif isinstance(widget, (QtWidgets.QLabel, QtWidgets.QAbstractButton)):
        text = widget.text()
        if text:
            widget.setText(translate(text))
    elif isinstance(widget, QtWidgets.QLineEdit):
        widget.setPlaceholderText(translate(widget.placeholderText()))
    elif isinstance(widget, QtWidgets.QTabWidget):
        for index in range(widget.count()):
            widget.setTabText(index, translate(widget.tabText(index)))


def localize_app(main_window: QtWidgets.QMainWindow) -> None:
    """Switch the fully built main window, and all later messages, to Chinese."""
    global _enabled
    _enabled = True
    _install_qt_translations()
    for widget in main_window.findChildren(QtWidgets.QWidget):
        _translate_widget(widget)
    main_window.statusBar().showMessage(translate('ready'), 3000)
