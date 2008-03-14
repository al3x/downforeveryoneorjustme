#!/usr/bin/env ruby

%w( rubygems sinatra uri net/http erb ).each { |g| require g }
include ERB::Util

layout { File.read('views/layout.erb') }

def show(template, title="Down for everyone or just me?")
  @title = title
  erb(template)
end

get '/' do
  show :home
end

get '/q' do
  if params[:domain] =~ /downforeveryoneorjustme/
    @domain = h(params[:domain])
    show(:up, "It's just you.")
  else
    redirect "/#{params[:domain]}"
  end
end

['/:domain', '/:www.:domain', '/:www.:domain.:ext'].each do |route|
  get route do
    actual_domain = params[:domain]
    actual_domain = "#{params[:www]}.#{actual_domain}" if params[:www]          
    actual_domain = "#{actual_domain}.#{params[:ext]}" if params[:ext]
    
    if params[:format] != 'html'
      actual_domain = "#{actual_domain}.#{params[:format]}"
    else
      actual_domain = "#{actual_domain}.com" unless actual_domain =~ /\.\w+/
    end
    
    before_http = actual_domain
    actual_domain = "http://#{actual_domain}" unless actual_domain =~ /^http:\/\//

    uri = valid_uri(actual_domain)
  
    @domain = h(before_http)
  
    if uri == :invalid
      show(:huh, "Huh?")
    elsif is_up?(uri)
      show(:up, "It's just you.")
    else
      show(:down, "Panic!")
    end
  end
end

private

  def valid_uri(domain)
    uri = nil
    code = nil
    
    begin 
      uri = URI.parse(domain)
    rescue Exception
      return :invalid
    else
      return :invalid unless uri.class == URI::HTTP
    end
    
    uri
  end
  
  def is_up?(uri)  
    code = nil
      
    begin
      Net::HTTP.start(uri.host, uri.port) do |http|
        code = http.request_head("/").code
      end      
    rescue Exception => e
      return false
    else
      if code =~ /(200|301|302)/
        return true
      else
        return false
      end
    end
    
    false  
  end