"""
Email templates for different types of outreach campaigns.
"""

class EmailTemplates:
    """Pre-built email templates for various campaign types."""
    
    @staticmethod
    def get_guest_post_template():
        """Template for guest posting opportunities."""
        return {
            "name": "Guest Post Pitch",
            "subject": "Guest Post Proposal for {{site_name}}",
            "html_content": """
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <p>Hi {{name}},</p>
                
                <p>I hope this email finds you well. My name is {{author_name}}, and I'm a {{author_title}} with expertise in {{expertise_area}}.</p>
                
                <p>I've been following {{site_name}} and really appreciate the quality content you publish, especially your recent piece on {{recent_article}}. Your audience would be interested in the insights I have to share.</p>
                
                <p>I'd love to contribute a guest post to your site. Here are some topic ideas I have in mind:</p>
                
                <ul>
                    <li>{{topic_1}}</li>
                    <li>{{topic_2}}</li>
                    <li>{{topic_3}}</li>
                </ul>
                
                <p>Each piece would be:</p>
                <ul>
                    <li>1,500-2,000 words of original, high-quality content</li>
                    <li>Well-researched with credible sources</li>
                    <li>Tailored specifically for your audience</li>
                    <li>Include relevant examples and actionable tips</li>
                </ul>
                
                <p>You can see examples of my writing at {{portfolio_link}}.</p>
                
                <p>Would any of these topics be a good fit for {{site_name}}? I'm also open to writing about other topics that would be more valuable to your readers.</p>
                
                <p>Looking forward to the possibility of contributing to your excellent publication.</p>
                
                <p>Best regards,<br>
                {{author_name}}<br>
                {{author_email}}<br>
                {{author_website}}</p>
            </body>
            </html>
            """,
            "text_content": """
Hi {{name}},

I hope this email finds you well. My name is {{author_name}}, and I'm a {{author_title}} with expertise in {{expertise_area}}.

I've been following {{site_name}} and really appreciate the quality content you publish, especially your recent piece on {{recent_article}}. Your audience would be interested in the insights I have to share.

I'd love to contribute a guest post to your site. Here are some topic ideas I have in mind:

- {{topic_1}}
- {{topic_2}}
- {{topic_3}}

Each piece would be:
- 1,500-2,000 words of original, high-quality content
- Well-researched with credible sources
- Tailored specifically for your audience
- Include relevant examples and actionable tips

You can see examples of my writing at {{portfolio_link}}.

Would any of these topics be a good fit for {{site_name}}? I'm also open to writing about other topics that would be more valuable to your readers.

Looking forward to the possibility of contributing to your excellent publication.

Best regards,
{{author_name}}
{{author_email}}
{{author_website}}
            """
        }
    
    @staticmethod
    def get_collaboration_template():
        """Template for collaboration outreach."""
        return {
            "name": "Collaboration Opportunity",
            "subject": "Partnership Opportunity with {{company_name}}",
            "html_content": """
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <p>Hello {{name}},</p>
                
                <p>I'm {{sender_name}} from {{sender_company}}, and I've been impressed by {{company_name}}'s work in {{industry}}.</p>
                
                <p>I believe there's a great opportunity for our companies to collaborate. We specialize in {{our_specialty}} and have successfully partnered with companies like {{example_partners}} to achieve {{results}}.</p>
                
                <p>Here's what we could potentially collaborate on:</p>
                
                <ul>
                    <li>{{collaboration_idea_1}}</li>
                    <li>{{collaboration_idea_2}}</li>
                    <li>{{collaboration_idea_3}}</li>
                </ul>
                
                <p>Our collaboration could provide mutual benefits:</p>
                <ul>
                    <li><strong>For {{company_name}}:</strong> {{benefit_for_them}}</li>
                    <li><strong>For {{sender_company}}:</strong> {{benefit_for_us}}</li>
                </ul>
                
                <p>Would you be interested in a brief 15-minute call to explore this further? I'm available {{availability}} and can work around your schedule.</p>
                
                <p>Looking forward to hearing from you.</p>
                
                <p>Best regards,<br>
                {{sender_name}}<br>
                {{sender_title}}<br>
                {{sender_company}}<br>
                {{sender_phone}}<br>
                {{sender_email}}</p>
            </body>
            </html>
            """
        }
    
    @staticmethod
    def get_press_inquiry_template():
        """Template for press and media inquiries."""
        return {
            "name": "Press Inquiry",
            "subject": "Media Inquiry: {{story_topic}}",
            "html_content": """
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <p>Dear {{name}},</p>
                
                <p>I'm {{journalist_name}}, {{journalist_title}} at {{publication_name}}. I'm currently working on a story about {{story_topic}} and would love to include {{company_name}}'s perspective.</p>
                
                <p>I'm particularly interested in:</p>
                <ul>
                    <li>{{question_1}}</li>
                    <li>{{question_2}}</li>
                    <li>{{question_3}}</li>
                </ul>
                
                <p>The article will be published {{publication_timeline}} and is expected to reach {{audience_size}} readers. This could be a great opportunity for {{company_name}} to share your expertise with our audience.</p>
                
                <p>Would you or someone from your team be available for a brief interview? I can accommodate your schedule and we can do this via phone, video call, or email - whatever works best for you.</p>
                
                <p>My deadline is {{deadline}}, so I'd appreciate a response by {{response_deadline}}.</p>
                
                <p>Thank you for your time and consideration.</p>
                
                <p>Best regards,<br>
                {{journalist_name}}<br>
                {{journalist_title}}<br>
                {{publication_name}}<br>
                {{journalist_email}}<br>
                {{journalist_phone}}</p>
            </body>
            </html>
            """
        }
    
    @staticmethod
    def get_follow_up_template():
        """Template for follow-up emails."""
        return {
            "name": "Follow-up Email",
            "subject": "Following up on {{original_subject}}",
            "html_content": """
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <p>Hi {{name}},</p>
                
                <p>I hope you're doing well. I wanted to follow up on my previous email about {{original_topic}} that I sent on {{original_date}}.</p>
                
                <p>I understand you're busy, but I wanted to make sure my message didn't get lost in your inbox. {{brief_recap}}</p>
                
                <p>If the timing isn't right, I completely understand. However, if you're interested, I'd love to hear your thoughts or answer any questions you might have.</p>
                
                <p>Would it be helpful if I sent over {{additional_info}} to give you a better sense of what I'm proposing?</p>
                
                <p>Thanks again for your time, and I look forward to hearing from you.</p>
                
                <p>Best regards,<br>
                {{sender_name}}</p>
            </body>
            </html>
            """
        }
    
    @staticmethod
    def get_all_templates():
        """Get all available templates."""
        return {
            "guest_post": EmailTemplates.get_guest_post_template(),
            "collaboration": EmailTemplates.get_collaboration_template(),
            "press_inquiry": EmailTemplates.get_press_inquiry_template(),
            "follow_up": EmailTemplates.get_follow_up_template()
        }