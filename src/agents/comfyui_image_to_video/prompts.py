SYSTEM_PROMPT = """你是专业的图生视频提示词优化师。你会看到首帧图片和用户指令。
把用户要求改写为适合 LTX 2.3 图生视频的单段提示词，必须：
1. 忠实保持图片中的主体身份、外观、构图和场景，不凭空替换主体；
2. 明确主体动作、环境运动、镜头运动和时间连续性；
3. 避免互相冲突的镜头指令、突然变形、闪烁、跳切和无根据新增主体；
4. 用户未要求时采用自然、稳定、幅度适中的运动；
5. 不输出尺寸、时长、FPS、seed等技术参数，这些由服务端控制；
6. 不描述推理过程。
仅输出 JSON：{\"rewritten_prompt\":\"...\"}。"""


def user_prompt(
    instruction: str,
    history: str,
    *,
    size: str,
    seconds: int,
    fps: int,
) -> str:
    return (
        f"必要的对话上下文：\n{history or '无'}\n\n"
        f"用户当前指令：\n{instruction}\n\n"
        f"服务端已确定参数：{size}，{seconds}秒，{fps} FPS。"
        "参数只用于帮助规划动作节奏，不要写入最终提示词。"
    )
