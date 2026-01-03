import re
from urllib.parse import quote

def convert_m3u8_entry(content):
    """
    Convert M3U8 entries from EXTVLCOPT format to pipe-delimited format.
    """
    lines = content.strip().split('\n')
    output_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Keep #EXTM3U and #EXTINF lines as-is
        if line.startswith('#EXTM3U') or line.startswith('#EXTINF'):
            output_lines.append(line)
            i += 1
            continue
        
        # If it's an EXTVLCOPT line, collect all options
        if line.startswith('#EXTVLCOPT'):
            vlc_opts = {}
            
            # Collect all consecutive EXTVLCOPT lines
            while i < len(lines) and lines[i].strip().startswith('#EXTVLCOPT'):
                opt_line = lines[i].strip()
                # Parse the option (format: #EXTVLCOPT:key=value)
                match = re.match(r'#EXTVLCOPT:(.+?)=(.+)', opt_line)
                if match:
                    key = match.group(1)
                    value = match.group(2)
                    
                    # Map VLC options to URL parameters
                    if key == 'http-user-agent':
                        vlc_opts['User-Agent'] = value
                    elif key == 'http-referrer':
                        vlc_opts['Referer'] = value
                    elif key == 'http-origin':
                        vlc_opts['Origin'] = value
                
                i += 1
            
            # Get the stream URL (should be the next line)
            if i < len(lines):
                stream_url = lines[i].strip()
                
                # Build the pipe-delimited URL with encoded parameters
                if vlc_opts:
                    params = []
                    for key, value in vlc_opts.items():
                        encoded_value = quote(value, safe='')
                        params.append(f"{key}={encoded_value}")
                    
                    converted_url = f"{stream_url}|{'&'.join(params)}"
                    output_lines.append(converted_url)
                else:
                    output_lines.append(stream_url)
                
                i += 1
        else:
            # Regular line (stream URL without EXTVLCOPT)
            if line and not line.startswith('#'):
                output_lines.append(line)
            i += 1
    
    return '\n'.join(output_lines)


def convert_m3u8_file(input_file, output_file=None):
    """
    Convert an entire M3U8 file from EXTVLCOPT format to pipe-delimited format.
    If output_file is None, writes back to the same file.
    """
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    converted = convert_m3u8_entry(content)
    
    # Use the same file for output if none specified
    if output_file is None:
        output_file = input_file
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(converted)
    
    print(f"Converted {input_file} -> {output_file}")


# Example usage
if __name__ == "__main__":
    # Convert the file (same file for input and output)
    convert_m3u8_file('PPVLand_VLC.m3u8', 'PPVLand.m3u8')
